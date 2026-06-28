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

_yahoo_rotate = 0


def _market_of(sym: str) -> str:
    s = sym.upper()
    if s.endswith((".NS", ".BO")):
        return "india"
    if s.endswith(".L"):
        return "uk"
    return "us"


def _yahoo_news_url(sym: str) -> str:
    import urllib.parse
    region = "IN" if sym.endswith((".NS", ".BO")) else "GB" if sym.endswith(".L") else "US"
    return (
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s="
        + urllib.parse.quote(sym) + "&region=" + region + "&lang=en-US"
    )


async def fetch_feed(session: aiohttp.ClientSession, url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
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

    sem = asyncio.Semaphore(6)  # bounded concurrency: fast, but memory-safe on 512MB
    async with aiohttp.ClientSession() as session:
        async def _one(feed: dict[str, Any]):
            name = feed.get("name", "feed")
            async with sem:
                try:
                    body = await fetch_feed(session, feed["url"])
                    parsed = await asyncio.to_thread(feedparser.parse, body)
                    return feed, parsed
                except Exception as e:
                    logger.warning("Feed failed %s: %s", name, str(e)[:140])
                    return feed, None

        # Fetch ALL feeds concurrently — sequential fetching let one slow/dead
        # feed (e.g. a 12s timeout x 25 feeds) starve the whole crawl and leave
        # the news list empty. gather bounds the crawl to the slowest single feed.
        fetched = await asyncio.gather(*[_one(f) for f in feeds])

        # Yahoo per-symbol RSS backbone — reliable from datacenter IPs (the
        # news-site feeds above often 403/404 from a server). Pre-matched to
        # the symbol. Rotate through the universe so all symbols get covered.
        global _yahoo_rotate
        uni = sorted(s for s in universe_flat if s)
        ysym_fetched: list = []
        if uni:
            n = min(24, len(uni))
            start = _yahoo_rotate % len(uni)
            sample = (uni + uni)[start:start + n]
            _yahoo_rotate = (start + n) % len(uni)

            async def _ysym(sym: str):
                async with sem:
                    try:
                        body = await fetch_feed(session, _yahoo_news_url(sym))
                        parsed = await asyncio.to_thread(feedparser.parse, body)
                        return sym, parsed
                    except Exception as e:
                        logger.debug("Yahoo news failed %s: %s", sym, str(e)[:80])
                        return sym, None

            ysym_fetched = await asyncio.gather(*[_ysym(sym) for sym in sample])

        for sym, parsed in ysym_fetched:
            if not parsed:
                continue
            for entry in parsed.entries[:8]:
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
                symbol_hits[sym] = symbol_hits.get(sym, 0) + 1
                symbol_titles.setdefault(sym, [])
                if len(symbol_titles[sym]) < 30 and title not in symbol_titles[sym]:
                    symbol_titles[sym].append(title)
                headlines.append({
                    "published_at": pub_iso, "title": title, "link": link,
                    "source": "Yahoo " + sym, "market": _market_of(sym), "symbols": [sym],
                })
                await insert_news(pub_iso, title, link, "Yahoo " + sym, _market_of(sym), [sym])

        for feed, parsed in fetched:
            if not parsed:
                continue
            name = feed.get("name", "feed")
            market = feed.get("market", "global")
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