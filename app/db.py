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
                call_time TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings(earnings_date);
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