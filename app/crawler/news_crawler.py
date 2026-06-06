from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp
import feedparser

from app.db import insert_news
from app.universe import extract_tickers_from_text

logger = logging.getLogger(__name__)


async def fetch_feed(session: aiohttp.ClientSession, url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        return await resp.text()


async def crawl_news_feeds(
    feeds: list[dict[str, Any]],
    universe_flat: set[str],
    max_per_feed: int = 40,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, list[str]]]:
    """Return (headlines, symbol->count, symbol->recent titles)."""
    headlines: list[dict[str, Any]] = []
    symbol_hits: dict[str, int] = {}
    symbol_titles: dict[str, list[str]] = {}

    async with aiohttp.ClientSession() as session:
        for feed in feeds:
            name = feed.get("name", "feed")
            url = feed["url"]
            market = feed.get("market", "global")
            try:
                body = await fetch_feed(session, url)
                parsed = await asyncio.to_thread(feedparser.parse, body)
            except Exception as e:
                logger.warning("Feed failed %s: %s", name, e)
                continue

            for entry in parsed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue
                published = entry.get("published", "")
                try:
                    if published:
                        dt = parsedate_to_datetime(published)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        pub_iso = dt.astimezone(timezone.utc).isoformat()
                    else:
                        pub_iso = datetime.now(timezone.utc).isoformat()
                except Exception:
                    pub_iso = datetime.now(timezone.utc).isoformat()

                text = f"{title} {entry.get('summary', '')}"
                syms = extract_tickers_from_text(text, universe_flat)
                for s in syms:
                    symbol_hits[s] = symbol_hits.get(s, 0) + 1
                    symbol_titles.setdefault(s, [])
                    if len(symbol_titles[s]) < 30:
                        symbol_titles[s].append(title)

                item = {
                    "published_at": pub_iso,
                    "title": title,
                    "link": link,
                    "source": name,
                    "market": market,
                    "symbols": syms,
                }
                headlines.append(item)
                await insert_news(pub_iso, title, link, name, market, syms)

    headlines.sort(key=lambda x: x["published_at"], reverse=True)
    return headlines, symbol_hits, symbol_titles