from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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
                call_time TEXT,
                from_news INTEGER DEFAULT 0,
                news_title TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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

            -- Server-persisted watchlists (shared for instance; multi-user can be extended later with user_id)
            CREATE TABLE IF NOT EXISTS user_watchlist (
                symbol TEXT PRIMARY KEY,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_watchlist_added ON user_watchlist(added_at DESC);

            -- Personalized alert rules (e.g. score + rvol + investor; smart_money; earnings etc)
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_type TEXT NOT NULL,  -- 'score', 'smart_money', 'earnings', 'custom'
                condition_json TEXT NOT NULL,  -- JSON: {"min_buy_score":65,"min_rvol":2.0,"has_investor":true,"earnings_within_days":3,"investor_types":["india_legend","us_legend","politician"]}
                enabled INTEGER DEFAULT 1,
                last_triggered TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- Persisted triggered alerts (for history + multi-device replay). Rich investor text preserved.
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                rule_id INTEGER,
                rule_type TEXT,
                message TEXT NOT NULL,
                triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                buy_score REAL,
                details_json TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol, triggered_at DESC);
            CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts(triggered_at DESC);

            -- Portfolio / Paper Trading Journal (server-persisted, survives refresh; one open paper position per symbol)
            CREATE TABLE IF NOT EXISTS portfolio_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                market TEXT,
                side TEXT DEFAULT 'long',
                qty REAL NOT NULL,
                entry_price REAL NOT NULL,
                entry_score REAL,
                entry_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                sl REAL,
                target REAL,
                updated_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_portfolio_symbol ON portfolio_positions(symbol);

            CREATE TABLE IF NOT EXISTS trade_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,  -- 'buy' | 'close'
                price REAL,
                qty REAL,
                score_at_time REAL,
                notes TEXT,
                outcome_pnl REAL,  -- realized P&L on close (positive = profit)
                outcome_at TEXT,
                linked_position_id INTEGER,
                thesis_pos TEXT,   -- snapshot of positives at log/close for insight
                thesis_neg TEXT,   -- snapshot of negatives/risks
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_journal_symbol ON trade_journal(symbol, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_journal_linked ON trade_journal(linked_position_id);
            """
        )
        cur = await db.execute("PRAGMA table_info(earnings)")
        existing_cols = {row[1] for row in await cur.fetchall()}
        for col, ddl in {
            "call_time": "ALTER TABLE earnings ADD COLUMN call_time TEXT",
            "from_news": "ALTER TABLE earnings ADD COLUMN from_news INTEGER DEFAULT 0",
            "news_title": "ALTER TABLE earnings ADD COLUMN news_title TEXT",
            "created_at": "ALTER TABLE earnings ADD COLUMN created_at TEXT",
            "updated_at": "ALTER TABLE earnings ADD COLUMN updated_at TEXT",
        }.items():
            if col not in existing_cols:
                await db.execute(ddl)
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
    Enhanced: per-symbol yf cache (computed at query time, avoids re-fetch for multi-snap symbols),
    promotes confidence/buy/quality + factor data for edge stats + UI.
    """
    snaps = await recent_strong_snapshots(days=days, min_score=min_score, limit=limit)
    # Per-symbol closes cache so we yf only once per unique ticker even if multiple snaps
    _closes_cache: dict[str, "pd.Series"] = {}
    try:
        import pandas as pd  # yf returns pandas; engine already uses it
    except Exception:
        pd = None
    for s in snaps:
        try:
            payload = s.get("payload") or {}
            # Promote key fields for /api/edge + frontend use (reuse existing payload from price_crawler/analyze)
            s["buy_score"] = payload.get("buy_score") or payload.get("score") or s.get("score")
            s["quality_score"] = payload.get("quality_score")
            s["confidence_score"] = payload.get("confidence_score")
            s["factor_breakdown"] = payload.get("factor_breakdown") or payload.get("factor_details") or []
            created = s.get("created_at")
            if not created:
                s["outcomes"] = {"error": "insufficient data at signal time"}
                continue
            sym = s["symbol"]
            # Lazy import (kept local like original to avoid hard dep at module load)
            import yfinance as yf
            from datetime import datetime, timedelta
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if sym not in _closes_cache:
                start = (dt - timedelta(days=3)).date()
                end = (dt + timedelta(days=17)).date()
                hist = yf.download(sym, start=str(start), end=str(end), progress=False, auto_adjust=True)
                if hist is None or hist.empty:
                    _closes_cache[sym] = None
                else:
                    _closes_cache[sym] = hist["Close"] if "Close" in hist.columns else None
            closes = _closes_cache.get(sym)
            if closes is None or len(closes) == 0:
                s["outcomes"] = {"error": "no historical price data"}
                continue
            # Find closest price at or just before signal (use last available before dt)
            idx = closes.index.get_indexer([dt], method="pad")[0]
            if idx < 0:
                s["outcomes"] = {"error": "no price at signal time"}
                continue
            p0 = float(closes.iloc[idx])
            # Forward prices (relative to THIS signal time)
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
            # Max drawdown in forward window (simplified min close / p0 -1 )
            window_closes = closes.iloc[idx:idx+16] if idx+16 < len(closes) else closes.iloc[idx:]
            if len(window_closes) > 1:
                mdd = (window_closes.min() / p0 - 1) * 100
            else:
                mdd = 0.0
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


# ===================== Server Watchlists + Alert Rules (new) =====================

async def add_to_watchlist(symbol: str, notes: str = "") -> bool:
    """Add symbol to persisted watchlist. Idempotent."""
    sym = symbol.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO user_watchlist (symbol, notes) VALUES (?, ?)",
                (sym, notes or None),
            )
            await db.commit()
            return True
        except Exception:
            return False


async def remove_from_watchlist(symbol: str) -> None:
    sym = symbol.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_watchlist WHERE symbol = ?", (sym,))
        await db.commit()


async def list_watchlist() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT symbol, added_at, notes FROM user_watchlist ORDER BY added_at DESC"
        )
        return [dict(r) for r in await cur.fetchall()]


async def add_alert_rule(rule_type: str, condition: dict, enabled: bool = True) -> int:
    """Create rule. Returns new rule id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO alert_rules (rule_type, condition_json, enabled)
            VALUES (?, ?, ?)
            """,
            (rule_type, json.dumps(condition or {}), 1 if enabled else 0),
        )
        await db.commit()
        return cur.lastrowid


async def list_alert_rules() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, rule_type, condition_json, enabled, last_triggered, created_at FROM alert_rules ORDER BY created_at DESC"
        )
        out = []
        for r in await cur.fetchall():
            d = dict(r)
            try:
                d["condition"] = json.loads(d.get("condition_json") or "{}")
            except Exception:
                d["condition"] = {}
            d["enabled"] = bool(d.get("enabled", 1))
            out.append(d)
        return out


async def delete_alert_rule(rule_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM alert_rules WHERE id = ?", (int(rule_id),))
        await db.commit()


async def update_alert_rule_last_triggered(rule_id: int, ts: str | None = None) -> None:
    ts = ts or utc_now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE alert_rules SET last_triggered = ? WHERE id = ?",
            (ts, int(rule_id)),
        )
        await db.commit()


async def insert_alert(
    symbol: str,
    message: str,
    rule_id: int | None = None,
    rule_type: str | None = None,
    buy_score: float | None = None,
    details: dict | None = None,
) -> int:
    """Store a triggered alert. Returns id. Also logs high-severity to market_events for history."""
    sym = symbol.upper()
    now = utc_now()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO alerts (symbol, rule_id, rule_type, message, triggered_at, buy_score, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sym,
                rule_id,
                rule_type,
                message,
                now,
                buy_score,
                json.dumps(details or {}),
            ),
        )
        alert_id = cur.lastrowid
        await db.commit()

    # Bonus: log to market_events for unified history (high conviction investor moves etc.)
    try:
        await insert_market_event(
            {
                "event_key": f"alert:{sym}:{now[:19]}",
                "symbol": sym,
                "market": "us" if not sym.endswith((".NS", ".BO")) else "india",
                "event_type": "alert_trigger",
                "severity": 8.0 if "INVESTOR" in (message or "").upper() or "SMART" in (message or "").upper() else 5.0,
                "source": "alert_rule",
                "title": message[:200],
                "actor_name": (details or {}).get("investor_name"),
                "actor_role": rule_type or "rule",
                "published_at": now,
                "raw_payload": {"rule_id": rule_id, "alert_id": alert_id, "buy_score": buy_score},
            }
        )
    except Exception:
        pass
    return alert_id


async def recent_alerts(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT id, symbol, rule_id, rule_type, message, triggered_at, buy_score, details_json
            FROM alerts ORDER BY triggered_at DESC LIMIT ?
            """,
            (limit,),
        )
        out = []
        for r in await cur.fetchall():
            d = dict(r)
            try:
                d["details"] = json.loads(d.get("details_json") or "{}")
            except Exception:
                d["details"] = {}
            out.append(d)
        return out


def _get_metric(row: dict, key: str, default=None):
    """Helper to dig buy_score / rvol etc from snapshot row or analyze payload."""
    m = row.get("metrics") or row.get("m") or {}
    if key == "buy_score":
        return row.get("buy_score") or row.get("score") or m.get("buy_score") or m.get("score") or default
    if key == "rvol":
        return m.get("rvol") or m.get("relative_volume") or row.get("rvol") or default
    if key == "score":
        return row.get("score") or m.get("score") or default
    return m.get(key, row.get(key, default))


async def evaluate_rules_for_snapshot(data: dict | None = None, symbols_data: list[dict] | None = None) -> list[dict]:
    """
    Core evaluator. Reuses the shape from hot rows / analyze_symbol results + investor_events.
    Returns list of triggered alert dicts ready for insert + WS push.
    Supports example rules: {"min_buy_score":65, "min_rvol":2, "has_investor":true }
    + smart_money specific, earnings etc.
    """
    rules = await list_alert_rules()
    enabled_rules = [r for r in rules if r.get("enabled")]
    if not enabled_rules:
        return []

    # Collect candidate rows: prefer explicit symbols_data or hot from snapshot
    candidates: list[dict] = []
    if symbols_data:
        candidates = list(symbols_data)
    elif data:
        candidates = list(data.get("hot") or [])
        # also merge from hot_by_market if present
        for mkt in ("us", "india"):
            candidates.extend(data.get("hot_by_market", {}).get(mkt, []) or [])
    if not candidates:
        return []

    # Also fold in recent investor_events for "has_investor" and rich naming
    investor_map: dict[str, list[dict]] = {}
    inv_events = (data or {}).get("investor_events") or []
    for ev in inv_events[-50:]:
        s = (ev.get("symbol") or "").upper()
        if s:
            investor_map.setdefault(s, []).append(ev)

    triggered = []
    seen_trigger_keys = set()  # avoid dup per (symbol,rule) in one eval pass

    for rule in enabled_rules:
        cond = rule.get("condition") or {}
        min_bs = cond.get("min_buy_score") or cond.get("min_score")
        min_rvol = cond.get("min_rvol") or cond.get("rvol")
        has_investor = bool(cond.get("has_investor") or cond.get("has_smart_money") or cond.get("smart_money"))
        earnings_days = cond.get("earnings_within_days") or cond.get("earnings_in_days")
        investor_types = cond.get("investor_types") or []  # e.g. ["india_legend","politician"]
        rule_type = rule.get("rule_type", "custom")

        for row in candidates:
            sym = (row.get("symbol") or "").upper()
            if not sym:
                continue
            key = (sym, rule["id"])
            if key in seen_trigger_keys:
                continue

            bs = _get_metric(row, "buy_score")
            rvol = _get_metric(row, "rvol")
            sc = _get_metric(row, "score")

            match = True
            reasons = []

# ============ PORTFOLIO / PAPER TRADING JOURNAL HELPERS (v1) ============

async def upsert_portfolio_position(
    symbol: str,
    market: str,
    qty: float,
    entry_price: float,
    entry_score: float | None = None,
    notes: str | None = None,
    sl: float | None = None,
    target: float | None = None,
) -> int:
    """Insert or replace open paper position (one per symbol). Returns position id."""
    symbol = symbol.upper()
    now = utc_now()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Delete any prior for this sym to enforce one open paper pos
        await db.execute("DELETE FROM portfolio_positions WHERE symbol = ?", (symbol,))
        cur = await db.execute(
            """
            INSERT INTO portfolio_positions
                (symbol, market, side, qty, entry_price, entry_score, entry_at, notes, sl, target, updated_at)
            VALUES (?, ?, 'long', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                market or "us",
                float(qty),
                float(entry_price),
                entry_score,
                now,
                notes,
                sl,
                target,
                now,
            ),
        )
        await db.commit()
        return cur.lastrowid or 0


async def update_portfolio_position(
    symbol: str,
    notes: str | None = None,
    sl: float | None = None,
    target: float | None = None,
) -> bool:
    """Update notes / SL / target on an open position."""
    symbol = symbol.upper()
    now = utc_now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE portfolio_positions
            SET notes = COALESCE(?, notes),
                sl = COALESCE(?, sl),
                target = COALESCE(?, target),
                updated_at = ?
            WHERE symbol = ?
            """,
            (notes, sl, target, now, symbol),
        )
        await db.commit()
        return True


async def list_portfolio() -> list[dict]:
    """Return current open paper positions (for /api/portfolio)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM portfolio_positions ORDER BY updated_at DESC, created_at DESC"
        )
        rows = []
        for r in await cur.fetchall():
            d = dict(r)
            rows.append(d)
        return rows


async def delete_portfolio_position(symbol: str) -> bool:
    """Remove a position (used on close)."""
    symbol = symbol.upper()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM portfolio_positions WHERE symbol = ?", (symbol,))
        await db.commit()
        return True


async def record_trade_journal(
    symbol: str,
    action: str,
    price: float | None = None,
    qty: float | None = None,
    score_at_time: float | None = None,
    notes: str | None = None,
    outcome_pnl: float | None = None,
    linked_position_id: int | None = None,
    thesis_pos: str | None = None,
    thesis_neg: str | None = None,
) -> int:
    """Log a buy or close action to journal. Returns journal id."""
    symbol = symbol.upper()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO trade_journal
                (symbol, action, price, qty, score_at_time, notes, outcome_pnl, outcome_at, linked_position_id, thesis_pos, thesis_neg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                action,
                price,
                qty,
                score_at_time,
                notes,
                outcome_pnl,
                utc_now() if outcome_pnl is not None or action == "close" else None,
                linked_position_id,
                thesis_pos,
                thesis_neg,
            ),
        )
        await db.commit()
        return cur.lastrowid or 0


async def list_journal(limit: int = 100) -> list[dict]:
    """Return recent journal entries (newest first)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM trade_journal ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_performance_stats() -> dict[str, Any]:
    """Compute winrate / total realized PnL from journal closes. Open PnL simulated in API layer using live state."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT outcome_pnl FROM trade_journal WHERE action = 'close' AND outcome_pnl IS NOT NULL"
        )
        pnls = [float(r[0]) for r in await cur.fetchall() if r[0] is not None]
        closed = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        winrate = round((wins / closed * 100), 1) if closed else 0.0
        total_pnl = round(sum(pnls), 2)
        open_count = 0
        cur2 = await db.execute("SELECT COUNT(*) FROM portfolio_positions")
        open_count = (await cur2.fetchone())[0] or 0
        return {
            "closed_trades": closed,
            "open_positions": open_count,
            "winrate": winrate,
            "total_realized_pnl": total_pnl,
            "wins": wins,
            "losses": closed - wins,
        }



async def get_or_create_default_rules() -> list[dict]:
    """Stub for alerts subagent feature (seeds example rules if none). Returns list."""
    try:
        rules = await list_alert_rules()
        if rules:
            return rules
    except:
        pass
    # minimal defaults so server starts
    return []
