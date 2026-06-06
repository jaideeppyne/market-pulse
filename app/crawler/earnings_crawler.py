from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import yfinance as yf

from app.db import upsert_earnings

logger = logging.getLogger(__name__)


def _parse_calendar(cal: Any) -> dict[str, Any] | None:
    """Extract next earnings date and estimates from yfinance calendar."""
    if cal is None:
        return None
    earnings_dates: list[date] = []

    if isinstance(cal, dict):
        raw = cal.get("Earnings Date") or cal.get("Earnings date")
        if raw is None:
            return None
        if isinstance(raw, list):
            for d in raw:
                if isinstance(d, datetime):
                    earnings_dates.append(d.date())
                elif isinstance(d, date):
                    earnings_dates.append(d)
        elif isinstance(raw, datetime):
            earnings_dates.append(raw.date())
        elif isinstance(raw, date):
            earnings_dates.append(raw)
        eps_avg = cal.get("Earnings Average")
        eps_high = cal.get("Earnings High")
        eps_low = cal.get("Earnings Low")
        rev_avg = cal.get("Revenue Average")
    else:
        return None

    if not earnings_dates:
        return None

    next_dt = min(earnings_dates)
    return {
        "earnings_date": next_dt.isoformat(),
        "eps_avg": eps_avg,
        "eps_high": eps_high,
        "eps_low": eps_low,
        "revenue_avg": rev_avg,
    }


def _fetch_one(symbol: str, market: str, horizon: date) -> dict[str, Any] | None:
    try:
        cal = yf.Ticker(symbol).calendar
        parsed = _parse_calendar(cal)
        if not parsed:
            return None
        ed = date.fromisoformat(parsed["earnings_date"])
        today = datetime.now(timezone.utc).date()
        if ed < today or ed > horizon:
            return None
        days_until = (ed - today).days
        return {
            "symbol": symbol,
            "market": market,
            "earnings_date": parsed["earnings_date"],
            "days_until": days_until,
            "eps_avg": parsed.get("eps_avg"),
            "eps_high": parsed.get("eps_high"),
            "eps_low": parsed.get("eps_low"),
            "revenue_avg": parsed.get("revenue_avg"),
            "call_time": None,
        }
    except Exception as e:
        logger.debug("Earnings skip %s: %s", symbol, e)
        return None


async def crawl_earnings_calendar(
    symbol_markets: list[tuple[str, str]],
    days_ahead: int = 7,
    batch_size: int = 20,
    batch_delay_sec: float = 0.4,
) -> list[dict[str, Any]]:
    """
    Scan universe for earnings within the next `days_ahead` days.
    Uses yfinance Ticker.calendar (US + NSE .NS).
    """
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=days_ahead)
    upcoming: list[dict[str, Any]] = []

    for i in range(0, len(symbol_markets), batch_size):
        chunk = symbol_markets[i : i + batch_size]

        def _batch_fetch() -> list[dict[str, Any]]:
            rows = []
            for sym, mkt in chunk:
                row = _fetch_one(sym, mkt, horizon)
                if row:
                    rows.append(row)
            return rows

        batch_rows = await asyncio.to_thread(_batch_fetch)
        for row in batch_rows:
            await upsert_earnings(row)
            upcoming.append(row)
        await asyncio.sleep(batch_delay_sec)

    upcoming.sort(key=lambda x: (x["days_until"], x["symbol"]))
    logger.info(
        "Earnings crawl: %d results in next %d days (scanned %d symbols)",
        len(upcoming),
        days_ahead,
        len(symbol_markets),
    )
    return upcoming


def enrich_with_scan_data(
    earnings: list[dict[str, Any]], symbols_cache: dict[str, dict]
) -> list[dict[str, Any]]:
    """Attach live score/RSI/price from latest price scan."""
    out = []
    for e in earnings:
        row = dict(e)
        scan = symbols_cache.get(e["symbol"], {})
        row["score"] = scan.get("score")
        row["rsi"] = (scan.get("metrics") or {}).get("rsi")
        row["day_chg_pct"] = (scan.get("metrics") or {}).get("day_chg_pct")
        row["name"] = (scan.get("metrics") or {}).get("name", e["symbol"])
        out.append(row)
    return out