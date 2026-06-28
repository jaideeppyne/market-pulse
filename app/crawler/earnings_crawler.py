from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

import feedparser
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
    Uses yfinance + multi-site RSS scraping (Moneycontrol, ET, BS, Yahoo) for next-level coverage.
    Especially helps Indian companies where yf is weak.
    """
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=days_ahead)
    upcoming: list[dict[str, Any]] = []

    # yf part
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

    # Multi-site RSS scraping (scrap multiple websites, not single one)
    try:
        rss_results = await crawl_earnings_from_multiple_sites(symbol_markets, days_ahead)
        for r in rss_results:
            await upsert_earnings(r)
            upcoming.append(r)
    except Exception as e:
        logger.warning("Multi-site earnings RSS failed: %s", e)

    upcoming.sort(key=lambda x: (x["days_until"], x["symbol"]))
    logger.info(
        "Earnings crawl: %d results in next %d days (scanned %d symbols, multi-site included)",
        len(upcoming),
        days_ahead,
        len(symbol_markets),
    )
    return upcoming


def _parse_earnings_from_rss(feed_url: str, market: str = "global") -> list[dict[str, Any]]:
    """Scrape earnings info from RSS feeds (Moneycontrol, ET, etc.) for next level multi-site coverage."""
    results = []
    _STOP = {"RESULTS","RESULT","BOARD","MEETING","EARNINGS","REVENUE","PROFIT","LOSS",
             "QUARTER","ANNUAL","REPORT","STOCK","STOCKS","SHARE","SHARES","MARKET","NEWS",
             "INDIA","LIMITED","LTD","INC","CORP","THE","AND","FOR","WITH","FROM","NSE","BSE",
             "JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"}
    try:
        import urllib.request as _u
        _req = _u.Request(feed_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                          "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
        })
        with _u.urlopen(_req, timeout=12) as _r:  # noqa: S310
            _body = _r.read()
        feed = feedparser.parse(_body)
        for entry in feed.entries[:30]:
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            text = f"{title} {summary}"
            # Extract possible dates and symbols
            date_match = re.search(r'(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|July|June)?', text, re.I)
            symbols = [x for x in re.findall(r'\b([A-Z]{2,12}(?:\.NS)?)\b', text.upper()) if x.replace(".NS","") not in _STOP and len(x.replace(".NS","")) >= 3]
            if date_match and symbols:
                try:
                    day = int(date_match.group(1))
                    mon_str = (date_match.group(2) or "").lower()[:3]
                    mon_map = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
                    mon = mon_map.get(mon_str, datetime.now().month)
                    ed = date(datetime.now().year, mon, min(day, 28))
                    today = datetime.now(timezone.utc).date()
                    if ed < today:
                        ed = date(today.year + 1, mon, min(day, 28))
                    days_until = (ed - today).days
                    if 0 <= days_until <= 14:  # within 2 weeks
                        for sym in symbols[:3]:  # limit
                            results.append({
                                "symbol": sym if ".NS" in sym else sym + (".NS" if market == "india" else ""),
                                "market": market,
                                "earnings_date": ed.isoformat(),
                                "days_until": days_until,
                                "eps_avg": None,
                                "from_rss": True,
                                "news_title": title[:80],
                            })
                except:
                    pass
    except Exception as e:
        logger.debug("RSS earnings parse failed for %s: %s", feed_url, e)
    return results


async def crawl_earnings_from_multiple_sites(symbol_markets: list[tuple[str, str]], days_ahead: int = 7) -> list[dict[str, Any]]:
    """Next level: scrape multiple websites/RSS for earnings (beyond single yf). India focused feeds + global."""
    all_results = []
    feeds = [
        ("https://www.moneycontrol.com/rss/results.xml", "india"),
        ("https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms", "india"),
        ("https://www.business-standard.com/rss/corporate-6.rss", "india"),
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^NSEI&region=IN&lang=en-US", "india"),
    ]
    rss_lists = await asyncio.gather(
        *[asyncio.to_thread(_parse_earnings_from_rss, fu, mk) for fu, mk in feeds],
        return_exceptions=True,
    )
    for rr in rss_lists:
        if isinstance(rr, list):
            all_results.extend(rr)

    # Dedup and filter to horizon
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=days_ahead)
    seen = set()
    filtered = []
    for r in all_results:
        if r["symbol"] not in seen:
            ed = date.fromisoformat(r["earnings_date"])
            if today <= ed <= horizon:
                seen.add(r["symbol"])
                filtered.append(r)
    logger.info("Multi-site RSS earnings: %d additional from feeds", len(filtered))
    return filtered


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