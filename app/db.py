from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

import os

ROOT = Path(__file__).resolve().parents[1]
_default_db = ROOT / "data" / "market_pulse.db"
DB_PATH = Path(os.getenv("DB_PATH", _default_db))


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                published_at TEXT,
                title TEXT NOT NULL,
                link TEXT UNIQUE,
                source TEXT,
                market TEXT,
                symbols TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS scan_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                market TEXT,
                payload TEXT NOT NULL,
                score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at DESC);
            CREATE INDEX IF NOT EXISTS idx_snap_symbol ON scan_snapshots(symbol, created_at DESC);
            CREATE TABLE IF NOT EXISTS earnings (
                symbol TEXT PRIMARY KEY,
                market TEXT NOT NULL,
                earnings_date TEXT NOT NULL,
                days_until INTEGER,
                eps_avg REAL,
                eps_high REAL,
                eps_low REAL,
                revenue_avg REAL,
                from_news INTEGER DEFAULT 0,
                news_title TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings(earnings_date);

            CREATE TABLE IF NOT EXISTS investor_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                event_type TEXT NOT NULL,  -- insider_buy, ceo_buy, promoter_buy, fund_13f_new_position, politician_trade, bulk_block_deal
                investor_name TEXT NOT NULL,
                investor_quality TEXT,  -- e.g. "Legendary (historical CAGR...)"
                details TEXT,
                source TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_investor_symbol ON investor_events(symbol, created_at DESC);

            CREATE TABLE IF NOT EXISTS market_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT UNIQUE,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity REAL DEFAULT 0,
                source TEXT,
                title TEXT NOT NULL,
                link TEXT,
                actor_name TEXT,
                actor_role TEXT,
                amount REAL,
                raw_payload TEXT,
                published_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_market_events_symbol ON market_events(symbol, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_market_events_type ON market_events(event_type, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_market_events_created ON market_events(created_at DESC);
            """
        )
        await db.commit()


async def insert_news(
    published_at: str,
    title: str,
    link: str,
    source: str,
    market: str,
    symbols: list[str],
) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                """
                INSERT INTO news (published_at, title, link, source, market, symbols)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (published_at, title, link, source, market, json.dumps(symbols)),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def insert_snapshot(symbol: str, market: str, payload: dict, score: float) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO scan_snapshots (symbol, market, payload, score)
            VALUES (?, ?, ?, ?)
            """,
            (symbol, market, json.dumps(payload), score),
        )
        await db.commit()


async def recent_news(limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM news ORDER BY published_at DESC LIMIT ?
            """,
            (limit,),
        )
        rows = await cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["symbols"] = json.loads(d.get("symbols") or "[]")
            out.append(d)
        return out


async def upsert_earnings(row: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO earnings (
                symbol, market, earnings_date, days_until,
                eps_avg, eps_high, eps_low, revenue_avg, call_time, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                market=excluded.market,
                earnings_date=excluded.earnings_date,
                days_until=excluded.days_until,
                eps_avg=excluded.eps_avg,
                eps_high=excluded.eps_high,
                eps_low=excluded.eps_low,
                revenue_avg=excluded.revenue_avg,
                call_time=excluded.call_time,
                updated_at=excluded.updated_at
            """,
            (
                row["symbol"],
                row["market"],
                row["earnings_date"],
                row["days_until"],
                row.get("eps_avg"),
                row.get("eps_high"),
                row.get("eps_low"),
                row.get("revenue_avg"),
                row.get("call_time"),
                utc_now(),
            ),
        )
        await db.commit()


async def upcoming_earnings(days: int = 7) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM earnings ORDER BY earnings_date ASC")
        rows = []
        for r in await cur.fetchall():
            d = dict(r)
            try:
                ed = date.fromisoformat(d["earnings_date"][:10])
                d["days_until"] = (ed - today).days
            except (ValueError, TypeError):
                continue
            if 0 <= d["days_until"] <= days:
                rows.append(d)
        return rows


async def clear_stale_earnings(days: int = 7) -> None:
    """Remove earnings outside the window."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM earnings WHERE days_until < 0 OR days_until > ?",
            (days,),
        )
        await db.commit()


async def insert_market_event(event: dict) -> bool:
    """Insert one official/news-derived market event. Returns True for new rows."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                """
                INSERT INTO market_events (
                    event_key, symbol, market, event_type, severity, source, title,
                    link, actor_name, actor_role, amount, raw_payload, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.get("event_key"),
                    event["symbol"],
                    event.get("market", "us"),
                    event["event_type"],
                    event.get("severity", 0),
                    event.get("source"),
                    event.get("title") or event["event_type"],
                    event.get("link"),
                    event.get("actor_name"),
                    event.get("actor_role"),
                    event.get("amount"),
                    json.dumps(event.get("raw_payload") or {}),
                    event.get("published_at") or utc_now(),
                ),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def recent_market_events(limit: int = 100, symbol: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if symbol:
            cur = await db.execute(
                """
                SELECT * FROM market_events
                WHERE symbol = ?
                ORDER BY published_at DESC, created_at DESC
                LIMIT ?
                """,
                (symbol.upper(), limit),
            )
        else:
            cur = await db.execute(
                """
                SELECT * FROM market_events
                ORDER BY published_at DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = []
        for r in await cur.fetchall():
            d = dict(r)
            try:
                d["raw_payload"] = json.loads(d.get("raw_payload") or "{}")
            except Exception:
                d["raw_payload"] = {}
            rows.append(d)
        return rows


def db_file_size_mb() -> float:
    if DB_PATH.exists():
        return DB_PATH.stat().st_size / (1024 * 1024)
    return 0.0


async def run_retention_cleanup(
    news_keep_days: int = 7,
    snapshot_keep_days: int = 3,
    max_snapshots_per_symbol: int = 30,
    earnings_window_days: int = 7,
    vacuum: bool = True,
) -> dict[str, int]:
    """
    Delete old news and scan history so the SQLite file stays small.
    Earnings rows are one row per symbol (upsert) — only stale dates purged.
    """
    now = datetime.now(timezone.utc)
    news_cutoff = (now - timedelta(days=news_keep_days)).isoformat()
    snap_cutoff = (now - timedelta(days=snapshot_keep_days)).isoformat()
    stats = {"news_deleted": 0, "snapshots_deleted": 0, "earnings_deleted": 0}

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM news WHERE created_at < ? OR published_at < ?",
            (news_cutoff, news_cutoff),
        )
        stats["news_deleted"] = cur.rowcount

        cur = await db.execute(
            "DELETE FROM scan_snapshots WHERE created_at < ?",
            (snap_cutoff,),
        )
        stats["snapshots_deleted"] = cur.rowcount

        # Per-symbol cap: drop oldest snapshots beyond N
        if max_snapshots_per_symbol > 0:
            cur = await db.execute(
                """
                DELETE FROM scan_snapshots
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY symbol ORDER BY created_at DESC
                               ) AS rn
                        FROM scan_snapshots
                    ) WHERE rn > ?
                )
                """,
                (max_snapshots_per_symbol,),
            )
            stats["snapshots_deleted"] += cur.rowcount

        cur = await db.execute(
            "DELETE FROM earnings WHERE days_until < 0 OR days_until > ?",
            (earnings_window_days,),
        )
        stats["earnings_deleted"] = cur.rowcount

        await db.commit()

        if vacuum:
            await db.execute("VACUUM")

    stats["db_size_mb"] = round(db_file_size_mb(), 2)
    return stats


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def recent_strong_snapshots(days: int = 2, min_score: float = 55.0, limit: int = 80) -> list[dict]:
    """Return recent high-conviction snapshot rows for backtest/edge views and S+ history."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT symbol, market, score, payload, created_at
            FROM scan_snapshots
            WHERE created_at >= ? AND score >= ?
            ORDER BY created_at DESC, score DESC
            LIMIT ?
            """,
            (cutoff, min_score, limit),
        )
        rows = []
        for r in await cur.fetchall():
            d = dict(r)
            try:
                d["payload"] = json.loads(d.get("payload") or "{}")
            except Exception:
                d["payload"] = {}
            rows.append(d)
        return rows


async def snapshots_for_symbol(symbol: str, limit: int = 25) -> list[dict]:
    """Recent snapshots for one symbol (for watchlist score history and deltas)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT symbol, market, score, payload, created_at
            FROM scan_snapshots
            WHERE symbol = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (symbol, limit),
        )
        rows = []
        for r in await cur.fetchall():
            d = dict(r)
            try:
                d["payload"] = json.loads(d.get("payload") or "{}")
            except Exception:
                d["payload"] = {}
            rows.append(d)
        return rows


async def insert_investor_event(event: dict[str, Any]) -> None:
    """Store official insider/CEO/promoter/fund/politician event for history and UI."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO investor_events (symbol, event_type, investor_name, investor_quality, details, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                event_type=excluded.event_type,
                investor_name=excluded.investor_name,
                investor_quality=excluded.investor_quality,
                details=excluded.details,
                source=excluded.source,
                created_at=excluded.created_at
            """,
            (
                event.get("symbol"),
                event.get("event_type"),
                event.get("investor_name"),
                event.get("investor_quality"),
                event.get("details"),
                event.get("source"),
                event.get("created_at") or utc_now(),
            ),
        )
        await db.commit()


async def recent_strong_snapshots_with_outcomes(days: int = 2, min_score: float = 55.0, limit: int = 80) -> list[dict]:
    """Return recent high-conviction snapshots with computed forward returns, drawdown, hit rate etc.
    This makes the engine self-validating by attaching post-signal outcomes using historical prices.
    """
    snaps = await recent_strong_snapshots(days=days, min_score=min_score, limit=limit)
    # Compute outcomes for each
    for s in snaps:
        try:
            payload = s.get("payload") or {}
            price_at = payload.get("metrics", {}).get("price")
            created = s.get("created_at")
            if not price_at or not created:
                s["outcomes"] = {"error": "insufficient data at signal time"}
                continue
            sym = s["symbol"]
            # Fetch historical prices around signal time + forward windows
            # Use yf to get daily closes from signal-1d to signal+15d or so
            import yfinance as yf
            from datetime import datetime, timedelta
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            start = (dt - timedelta(days=2)).date()
            end = (dt + timedelta(days=16)).date()
            hist = yf.download(sym, start=str(start), end=str(end), progress=False, auto_adjust=True)
            if hist.empty:
                s["outcomes"] = {"error": "no historical price data"}
                continue
            closes = hist["Close"]
            # Find closest price at or just before signal (use last available before dt)
            idx = closes.index.get_indexer([dt], method="pad")[0]
            if idx < 0:
                s["outcomes"] = {"error": "no price at signal time"}
                continue
            p0 = float(closes.iloc[idx])
            # Forward prices
            def fwd_price(days):
                fwd_dt = dt + timedelta(days=days)
                fidx = closes.index.get_indexer([fwd_dt], method="bfill")[0]
                if fidx < 0 or fidx >= len(closes):
                    return None
                return float(closes.iloc[fidx])
            p1 = fwd_price(1)
            p3 = fwd_price(3)
            p7 = fwd_price(7)
            p14 = fwd_price(14)
            # Max drawdown in window (simplified: min close / p0 -1 in next 14d)
            window_closes = closes.iloc[idx:idx+15] if idx+15 < len(closes) else closes.iloc[idx:]
            if len(window_closes) > 1:
                mdd = (window_closes.min() / p0 - 1) * 100
            else:
                mdd = 0
            ret1 = ((p1 / p0 - 1) * 100) if p1 else None
            ret3 = ((p3 / p0 - 1) * 100) if p3 else None
            ret7 = ((p7 / p0 - 1) * 100) if p7 else None
            ret14 = ((p14 / p0 - 1) * 100) if p14 else None
            s["outcomes"] = {
                "ret_1d": round(ret1, 2) if ret1 is not None else None,
                "ret_3d": round(ret3, 2) if ret3 is not None else None,
                "ret_7d": round(ret7, 2) if ret7 is not None else None,
                "ret_14d": round(ret14, 2) if ret14 is not None else None,
                "max_dd_14d": round(mdd, 2),
                "p0": round(p0, 2),
            }
        except Exception as e:
            s["outcomes"] = {"error": str(e)[:100]}
    return snaps
