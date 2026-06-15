from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
import feedparser

logger = logging.getLogger(__name__)

async def fetch_edgar_form4(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """Poll SEC EDGAR for recent Form 4 (insider/CEO/director buys). Returns parsed events."""
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=include&start=0&count=100&output=atom"
    headers = {"User-Agent": "MarketPulse/1.0 (contact@example.com)"}
    events = []
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return events
            text = await resp.text()
            feed = feedparser.parse(text)
            for entry in feed.entries[:50]:
                title = entry.get("title", "")
                if "4" not in title and "Form 4" not in title:
                    continue
                summary = entry.get("summary", "")
                # Simple parse for insider name, company, shares (real parser would use XML)
                # For demo, extract from title/summary
                if "buy" in (title + summary).lower() or "acquir" in (title + summary).lower():
                    events.append({
                        "event_type": "insider_buy",
                        "investor_name": "SEC Insider (Form 4)",
                        "symbol": None,  # resolved later via alias
                        "details": title[:200],
                        "source": "SEC EDGAR Form 4",
                        "created_at": entry.get("updated", datetime.now(timezone.utc).isoformat()),
                    })
    except Exception as e:
        logger.warning("EDGAR Form 4 fetch failed: %s", e)
    return events


async def fetch_nse_promoter_disclosures(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """Poll NSE/BSE style for promoter/director acquisitions (use news/RSS as proxy for free)."""
    # For real, would use NSE API or RSS; here leverage existing multi-site but add demo
    events = []
    # In practice, use the news feeds already in config for "promoter buy" etc.
    # This is placeholder to integrate; real would parse specific NSE/BSE corp ann.
    return events


async def crawl_insider_filings() -> list[dict[str, Any]]:
    """Main: fetch official US Form 4 + India promoter disclosures (live, fast)."""
    events: list[dict[str, Any]] = []
    async with aiohttp.ClientSession() as session:
        events.extend(await fetch_edgar_form4(session))
        events.extend(await fetch_nse_promoter_disclosures(session))
    # Alias resolver stub (see news_crawler enhancement)
    for e in events:
        if not e.get("symbol"):
            # Would resolve from details/company name
            pass
    logger.info("Insider crawler: %d events", len(events))
    return events
