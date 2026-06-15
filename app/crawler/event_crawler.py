from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from app.db import insert_market_event
from app.universe import extract_tickers_from_text

logger = logging.getLogger(__name__)

SEC_HEADERS = {
    "User-Agent": "MarketPulse/1.0 contact=local@marketpulse",
    "Accept-Encoding": "gzip, deflate",
}
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FORM4_ATOM = (
    "https://www.sec.gov/cgi-bin/browse-edgar?"
    "action=getcurrent&type=4&owner=only&count=100&output=atom"
)

CEO_RX = re.compile(r"\b(ceo|chief executive|managing director|md)\b", re.I)
CFO_RX = re.compile(r"\b(cfo|chief financial)\b", re.I)
BUY_NEWS_RX = re.compile(
    r"\b(ceo|cfo|director|insider|promoter|founder|chairman|md|management)\b"
    r".{0,80}\b(buy|buys|bought|purchase|purchases|acquires|picked up|increases stake)\b|"
    r"\b(buy|buys|bought|purchase|purchases|acquires|increases stake)\b"
    r".{0,80}\b(ceo|cfo|director|insider|promoter|founder|chairman|md|management)\b",
    re.I,
)
BLOCK_DEAL_RX = re.compile(r"\b(block deal|bulk deal|large trade|promoter stake|open market purchase)\b", re.I)

_sec_ticker_cache: dict[str, str] | None = None


def _event_key(*parts: str) -> str:
    raw = "|".join(p or "" for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


async def _sec_ticker_map(client: httpx.AsyncClient) -> dict[str, str]:
    global _sec_ticker_cache
    if _sec_ticker_cache is not None:
        return _sec_ticker_cache
    out: dict[str, str] = {}
    try:
        resp = await client.get(SEC_TICKERS_URL, headers=SEC_HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for row in data.values():
            cik = str(row.get("cik_str", "")).lstrip("0")
            ticker = str(row.get("ticker", "")).upper()
            if cik and ticker:
                out[cik] = ticker
    except Exception as e:
        logger.warning("SEC ticker map failed: %s", e)
    _sec_ticker_cache = out
    return out


def _text(root: ET.Element, path: str) -> str:
    node = root.find(path)
    return (node.text or "").strip() if node is not None and node.text else ""


def _float_text(root: ET.Element, path: str) -> float | None:
    raw = _text(root, path)
    try:
        return float(raw.replace(",", "")) if raw else None
    except ValueError:
        return None


async def _find_primary_xml(client: httpx.AsyncClient, index_url: str) -> str | None:
    try:
        resp = await client.get(index_url, headers=SEC_HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except Exception:
        return None
    matches = re.findall(r'href="([^"]+\.xml)"', html, flags=re.I)
    for href in matches:
        if "FilingSummary" in href:
            continue
        if href.startswith("/"):
            return "https://www.sec.gov" + href
        if href.startswith("http"):
            return href
        return index_url.rsplit("/", 1)[0] + "/" + href
    return None


async def _parse_form4_xml(client: httpx.AsyncClient, xml_url: str) -> dict[str, Any] | None:
    try:
        resp = await client.get(xml_url, headers=SEC_HEADERS, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception:
        return None

    symbol = _text(root, ".//issuerTradingSymbol").upper()
    owner = _text(root, ".//reportingOwnerId/rptOwnerName")
    officer_title = _text(root, ".//reportingOwnerRelationship/officerTitle")
    is_director = _text(root, ".//reportingOwnerRelationship/isDirector") == "1"
    is_officer = _text(root, ".//reportingOwnerRelationship/isOfficer") == "1"
    role_bits = []
    if officer_title:
        role_bits.append(officer_title)
    if is_director:
        role_bits.append("Director")
    if is_officer and not officer_title:
        role_bits.append("Officer")
    role = ", ".join(role_bits) or None

    best_tx: dict[str, Any] | None = None
    for tx in root.findall(".//nonDerivativeTransaction"):
        code = _text(tx, ".//transactionCoding/transactionCode").upper()
        acquired = _text(tx, ".//transactionAmounts/transactionAcquiredDisposedCode/value").upper()
        if code != "P" or acquired != "A":
            continue
        shares = _float_text(tx, ".//transactionAmounts/transactionShares/value") or 0
        price = _float_text(tx, ".//transactionAmounts/transactionPricePerShare/value") or 0
        value = shares * price if shares and price else None
        if best_tx is None or (value or 0) > (best_tx.get("amount") or 0):
            best_tx = {"shares": shares, "price": price, "amount": value}

    if not symbol or best_tx is None:
        return None

    event_type = "insider_open_market_buy"
    severity = 8.0
    if role and CEO_RX.search(role):
        event_type = "ceo_buy"
        severity = 10.0
    elif role and CFO_RX.search(role):
        event_type = "cfo_buy"
        severity = 9.0
    elif is_director:
        event_type = "director_buy"
        severity = 8.5

    return {
        "symbol": symbol,
        "market": "us",
        "event_type": event_type,
        "severity": severity,
        "source": "SEC Form 4",
        "title": f"{owner or 'Insider'} {role or 'insider'} bought {symbol}",
        "link": xml_url,
        "actor_name": owner,
        "actor_role": role,
        "amount": best_tx.get("amount"),
        "raw_payload": best_tx,
    }


async def crawl_sec_form4_events(limit: int = 80) -> list[dict[str, Any]]:
    """Poll SEC current Form 4 feed and return structured open-market buy events."""
    events: list[dict[str, Any]] = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        ticker_map = await _sec_ticker_map(client)
        try:
            resp = await client.get(SEC_FORM4_ATOM, headers=SEC_HEADERS, timeout=25)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except Exception as e:
            logger.warning("SEC Form 4 feed failed: %s", e)
            return events

        entries = feed.entries[:limit]
        for entry in entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("updated") or entry.get("published") or datetime.now(timezone.utc).isoformat()
            xml_url = await _find_primary_xml(client, link) if link else None
            event = await _parse_form4_xml(client, xml_url) if xml_url else None
            if not event:
                cik_match = re.search(r"\((\d{5,10})\)", title)
                symbol = ticker_map.get(cik_match.group(1).lstrip("0")) if cik_match else None
                if not symbol:
                    continue
                event = {
                    "symbol": symbol,
                    "market": "us",
                    "event_type": "sec_form4_filing",
                    "severity": 5.0,
                    "source": "SEC Form 4",
                    "title": title,
                    "link": link,
                }
            event["published_at"] = published
            event["event_key"] = _event_key(event["source"], event["event_type"], event["symbol"], link or xml_url or title)
            events.append(event)
            await asyncio.sleep(0.12)
    return events


def derive_news_events(news_items: list[dict[str, Any]], universe_flat: set[str]) -> list[dict[str, Any]]:
    """Turn high-signal insider/promoter/block-deal headlines into structured events."""
    events: list[dict[str, Any]] = []
    for item in news_items[:200]:
        title = item.get("title") or ""
        if not title:
            continue
        is_buy = bool(BUY_NEWS_RX.search(title))
        is_block = bool(BLOCK_DEAL_RX.search(title))
        if not is_buy and not is_block:
            continue
        syms = item.get("symbols") or extract_tickers_from_text(title, universe_flat)
        for sym in syms[:5]:
            market = "india" if sym.endswith((".NS", ".BO")) else "us"
            event_type = "promoter_or_insider_buy" if is_buy else "bulk_block_deal"
            if market == "us" and is_buy:
                event_type = "news_insider_buy"
            severity = 8.0 if is_buy else 7.0
            if CEO_RX.search(title):
                event_type = "ceo_buy_news"
                severity = 9.0
            events.append(
                {
                    "event_key": _event_key("news", event_type, sym, item.get("link") or title),
                    "symbol": sym,
                    "market": market,
                    "event_type": event_type,
                    "severity": severity,
                    "source": item.get("source") or "news",
                    "title": title,
                    "link": item.get("link"),
                    "published_at": item.get("published_at"),
                    "raw_payload": {"news_market": item.get("market")},
                }
            )
    return events


async def persist_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    new_events = []
    for event in events:
        try:
            if await insert_market_event(event):
                new_events.append(event)
        except Exception as e:
            logger.debug("market event insert skipped: %s", e)
    return new_events
