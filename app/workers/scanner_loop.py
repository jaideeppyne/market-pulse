from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.crawler.earnings_crawler import crawl_earnings_calendar
from app.crawler.event_crawler import (
    crawl_sec_form4_events,
    derive_news_events,
    persist_events,
)
from app.crawler.insider_crawler import crawl_insider_filings
from app.crawler.news_crawler import crawl_news_feeds
from app.crawler.price_crawler import scan_symbols
from app.crawler.quick_prices import quick_refresh_symbols
from app.db import clear_stale_earnings, insert_investor_event, run_retention_cleanup
from app.engine.candidate_scanner import build_event_candidates
from app.state import AppState

logger = logging.getLogger(__name__)


class ScannerLoop:
    def __init__(self, cfg: dict[str, Any], state: AppState):
        self.cfg = cfg
        self.state = state
        self._running = False
        self._universe_flat: set[str] = set()
        self._news_counts: dict[str, int] = {}
        self._news_titles: dict[str, list[str]] = {}
        self._symbol_failures: dict[str, int] = {}
        self._symbol_quarantine_until: dict[str, float] = {}
        self._scan_offsets: dict[str, int] = {}

    def _eligible_pairs(self, pairs: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], int]:
        """Skip symbols that repeatedly produced no usable market data.

        This is intentionally in-memory and conservative. On-demand analysis
        still tries any ticker the user types; the quarantine only protects the
        live scanner from hammering stale/delisted names every cycle.
        """
        now = time.time()
        active: list[tuple[str, str]] = []
        skipped = 0
        for sym, market in pairs:
            until = self._symbol_quarantine_until.get(sym, 0)
            if until > now:
                skipped += 1
                continue
            if until:
                self._symbol_quarantine_until.pop(sym, None)
                self._symbol_failures.pop(sym, None)
            active.append((sym, market))
        return active, skipped

    def _record_symbol_health(self, requested: list[str], results: list[dict]) -> None:
        if not requested:
            return
        returned = {str(r.get("symbol") or "").upper() for r in results}
        returned.discard("")
        for sym in returned:
            self._symbol_failures.pop(sym, None)
            self._symbol_quarantine_until.pop(sym, None)

        # If a large whole batch returns nothing, treat it as provider/rate-limit
        # risk and avoid quarantining valid symbols accidentally.
        count_failures = bool(returned) or len(requested) <= 4
        if not count_failures:
            return

        now = time.time()
        for sym in requested:
            if sym in returned:
                continue
            misses = self._symbol_failures.get(sym, 0) + 1
            self._symbol_failures[sym] = misses
            if misses >= 2:
                self._symbol_quarantine_until[sym] = now + 6 * 3600

    def _all_symbols(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for sym in self.state.universe.get("us", []):
            pairs.append((sym, "us"))
        for sym in self.state.universe.get("india", []):
            pairs.append((sym, "india"))
        for sym in self.state.universe.get("uk", []):
            pairs.append((sym, "uk"))
        return pairs

    def _dedupe_symbols(self, symbols: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for sym in symbols:
            key = str(sym or "").upper()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    def _rotating_market_window(self, market: str, symbols: list[str], limit: int | None) -> list[str]:
        symbols = self._dedupe_symbols(symbols)
        if not limit or limit <= 0 or len(symbols) <= limit:
            return symbols
        start = self._scan_offsets.get(market, 0) % len(symbols)
        window = [symbols[(start + i) % len(symbols)] for i in range(limit)]
        self._scan_offsets[market] = (start + limit) % len(symbols)
        return window

    def _build_live_scan_pairs(self, events_by_symbol: dict[str, list[dict]]) -> list[tuple[str, str]]:
        """Build the live hot-mover scan from the configured universe, not fixed tickers.

        A configurable rotating window keeps each pass bounded for yfinance while
        eventually covering the whole configured US/India/UK universe. Event-led
        symbols are always included on top of the regular universe window.
        """
        scfg = self.cfg.get("scanner", {})
        try:
            live_limit = int(scfg.get("live_symbols_per_market", 0))
        except (TypeError, ValueError):
            live_limit = 0

        pairs: list[tuple[str, str]] = []
        seen: set[str] = set()
        universe = self.state.universe or {}
        for market in ("india", "us", "uk"):
            symbols = self._rotating_market_window(market, list(universe.get(market, [])), live_limit)
            for sym in symbols:
                if sym in seen:
                    continue
                pairs.append((sym, market))
                seen.add(sym)

        for sym, events in events_by_symbol.items():
            key = str(sym or "").upper()
            if not key or key in seen:
                continue
            event_market = (events[0] or {}).get("market") if events else None
            market = event_market or ("india" if key.endswith((".NS", ".BO")) else "uk" if key.endswith(".L") else "us")
            pairs.append((key, market))
            seen.add(key)

        return pairs

    async def news_loop(self) -> None:
        interval = self.cfg["scanner"]["news_scan_interval_sec"]
        feeds = self.cfg.get("news", {}).get("feeds", [])
        max_per = self.cfg.get("news", {}).get("max_headlines_per_feed", 40)

        while self._running:
            try:
                headlines, counts, titles = await crawl_news_feeds(
                    feeds, self._universe_flat, max_per
                )
                for k, v in counts.items():
                    self._news_counts[k] = self._news_counts.get(k, 0) + v
                for sym, tlist in titles.items():
                    self._news_titles.setdefault(sym, [])
                    self._news_titles[sym] = (tlist + self._news_titles[sym])[:40]
                await self.state.update_news(
                    headlines, dict(self._news_counts), dict(self._news_titles)
                )
                logger.info("News crawl: %d headlines, %d symbols tagged", len(headlines), len(counts))
            except Exception as e:
                logger.exception("News loop error: %s", e)
            await asyncio.sleep(interval)

    async def price_loop(self) -> None:
        scfg = self.cfg["scanner"]
        interval = scfg["price_scan_interval_sec"]
        batch_size = scfg["batch_size"]
        delay = scfg["batch_delay_sec"]
        threshold = scfg["hot_score_threshold"]
        top_n = scfg.get("top_n", 200)
        weights = self.cfg.get("signals", {}).get("weights", {})
        self.state.hot_top_n = top_n
        self.state.hot_score_threshold = threshold

        while self._running:
            try:
                async with self.state.lock:
                    events_by_symbol = {
                        sym: list(events)
                        for sym, events in self.state.events_by_symbol.items()
                    }
                pairs = self._build_live_scan_pairs(events_by_symbol)
                pairs, skipped_quarantined = self._eligible_pairs(pairs)
                if skipped_quarantined:
                    async with self.state.lock:
                        self.state.stats["symbols_quarantined"] = skipped_quarantined

                # Prioritize India chunks first in batching for better live coverage of India stocks
                # (helps prevent India tab being stuck on just RELIANCE or few names while US dominates)
                india_p = [p for p in pairs if p[1] == "india"]
                us_p = [p for p in pairs if p[1] != "india"]
                pairs = india_p + us_p
                all_results: list[dict] = []
                batch_total = max(1, (len(pairs) + batch_size - 1) // batch_size)
                batch_index = 0
                for i in range(0, len(pairs), batch_size):
                    if not self._running:
                        break
                    chunk = pairs[i : i + batch_size]
                    batch_index += 1
                    by_market: dict[str, list[str]] = {"us": [], "india": [], "uk": []}
                    for sym, mkt in chunk:
                        by_market[mkt].append(sym)
                    async with self.state.lock:
                        earn_map = dict(self.state.earnings_by_symbol)
                        news_titles = dict(self.state.news_titles_by_symbol)
                        events_by_symbol = {
                            sym: list(events)
                            for sym, events in self.state.events_by_symbol.items()
                        }
                    batch_results: list[dict] = []
                    for mkt, syms in by_market.items():
                        if syms:
                            # Split the (already small) live core into tiny sub-batches of 5 with sleep.
                            # yf free tier rate limits kill large-ish batches even for "core" lists, leading to 0 results.
                            # This makes live hot movers actually populate with real US/India stocks.
                            for j in range(0, len(syms), 5):
                                sub = syms[j:j+5]
                                try:
                                    res = await scan_symbols(
                                        sub,
                                        mkt,
                                        self._news_counts,
                                        weights,
                                        earn_map,
                                        news_titles,
                                        events_by_symbol,
                                    )
                                    batch_results.extend(res)
                                    all_results.extend(res)
                                    self._record_symbol_health(sub, res)
                                except Exception:
                                    logger.warning("Price sub-batch error for %s (skipped)", mkt)
                                await asyncio.sleep(1.5)  # gentle sleep to respect yf free limits for live scan
                    # Live UI update after each batch (re-sort hot list immediately)
                    await self.state.update_scan(
                        batch_results,
                        threshold,
                        partial=True,
                        batch_index=batch_index,
                        batch_total=batch_total,
                        attempted_count=len(chunk),
                    )
                    await asyncio.sleep(delay)

                if pairs and not all_results:
                    logger.warning(
                        "Price scan produced zero results from %d attempted symbols",
                        len(pairs),
                    )
                await self.state.update_scan(
                    all_results,
                    threshold,
                    partial=False,
                    batch_index=batch_total,
                    batch_total=batch_total,
                    attempted_count=len(pairs),
                )
                # Refresh earnings panel with latest scores
                async with self.state.lock:
                    earn_list = list(self.state.earnings)
                if earn_list:
                    await self.state.update_earnings(earn_list)
                logger.info(
                    "Price scan complete: %d symbols, %d hot",
                    len(all_results),
                    len([r for r in all_results if r["score"] >= threshold]),
                )
                # decay news counts slowly so old news fades
                for k in list(self._news_counts.keys()):
                    self._news_counts[k] = max(0, self._news_counts[k] - 1)
            except Exception:
                logger.exception("Price loop error")
            await asyncio.sleep(interval)

    async def event_loop(self) -> None:
        """Ingest structured market events and maintain event-driven candidates."""
        scfg = self.cfg.get("scanner", {})
        interval = scfg.get("event_scan_interval_sec", 180)
        sec_limit = scfg.get("event_sec_form4_limit", 40)

        while self._running:
            try:
                async with self.state.lock:
                    news_items = list(self.state.news[:250])

                events = await crawl_sec_form4_events(limit=sec_limit)
                events.extend(derive_news_events(news_items, self._universe_flat))
                new_events = await persist_events(events)

                if new_events:
                    await self.state.update_events(new_events)

                async with self.state.lock:
                    events_by_symbol = {
                        sym: list(items)
                        for sym, items in self.state.events_by_symbol.items()
                    }
                    symbols_cache = dict(self.state.symbols)
                candidates = build_event_candidates(
                    events_by_symbol,
                    symbols_cache,
                    limit=scfg.get("event_candidate_limit", 120),
                )
                await self.state.update_candidates(candidates)

                logger.info(
                    "Event loop: %d crawled, %d new, %d candidates",
                    len(events),
                    len(new_events),
                    len(candidates),
                )
            except Exception:
                logger.exception("Event loop error")
            await asyncio.sleep(interval)

    async def cleanup_loop(self) -> None:
        rcfg = self.cfg.get("retention", {})
        interval_hours = rcfg.get("cleanup_interval_hours", 12)
        interval_sec = max(3600, int(interval_hours * 3600))

        while self._running:
            try:
                stats = await run_retention_cleanup(
                    news_keep_days=rcfg.get("news_keep_days", 7),
                    snapshot_keep_days=rcfg.get("scan_snapshots_keep_days", 3),
                    max_snapshots_per_symbol=rcfg.get("max_snapshots_per_symbol", 30),
                    earnings_window_days=self.cfg.get("earnings", {}).get("days_ahead", 7),
                    vacuum=rcfg.get("vacuum_on_cleanup", True),
                )
                async with self.state.lock:
                    self.state.stats["last_cleanup"] = datetime.now(timezone.utc).isoformat()
                    self.state.stats["db_size_mb"] = stats.get("db_size_mb")
                    self.state.stats["cleanup_deleted"] = stats
                logger.info("DB retention cleanup: %s", stats)
            except Exception:
                logger.exception("Cleanup loop error")
            await asyncio.sleep(interval_sec)

    async def earnings_loop(self) -> None:
        ecfg = self.cfg.get("earnings", {})
        interval = ecfg.get("scan_interval_sec", 1800)
        days_ahead = ecfg.get("days_ahead", 7)
        batch_size = ecfg.get("batch_size", 20)
        delay = ecfg.get("batch_delay_sec", 0.4)

        while self._running:
            try:
                pairs = self._all_symbols()
                upcoming = await crawl_earnings_calendar(
                    pairs,
                    days_ahead=days_ahead,
                    batch_size=batch_size,
                    batch_delay_sec=delay,
                )
                await clear_stale_earnings(days_ahead)
                await self.state.update_earnings(upcoming)
            except Exception:
                logger.exception("Earnings loop error")
            await asyncio.sleep(interval)

    async def insider_loop(self) -> None:
        """Official insider/CEO/promoter/fund/politician scanner (two-tier candidate trigger).
        Polls SEC EDGAR Form 4 + NSE/BSE disclosures every 30s for fastest detection.
        Stores events, pushes via WS, triggers deep scoring on hits.
        """
        interval = self.cfg.get("scanner", {}).get("insider_scan_interval_sec", 30)
        while self._running:
            try:
                events = await crawl_insider_filings()
                for ev in events:
                    await insert_investor_event(ev)
                    # Push live via state (WS will broadcast)
                    async with self.state.lock:
                        self.state.investor_events = getattr(self.state, "investor_events", [])
                        self.state.investor_events.append(ev)
                        if len(self.state.investor_events) > 100:
                            self.state.investor_events = self.state.investor_events[-100:]
                    # Mark symbol for Tier 2 deep if known
                    if ev.get("symbol"):
                        # In real: add to candidate queue for deep scan
                        pass
                    # Trigger broadcast so rules eval (for smart_money / investor personalized alerts) + WS happens immediately
                    self.state.broadcast_event.set()
                logger.info("Insider loop: %d events (Form 4 / promoter / bulk)", len(events))
            except Exception as e:
                logger.warning("Insider loop error (non-fatal): %s", e)
            await asyncio.sleep(interval)

    async def start(self) -> None:
        self._running = True
        self._universe_flat = set(self.state.universe.get("us", [])) | set(
            self.state.universe.get("india", [])
        ) | set(self.state.universe.get("uk", []))
        # Run cleanup once immediately, then on schedule
        rcfg = self.cfg.get("retention", {})
        try:
            await run_retention_cleanup(
                news_keep_days=rcfg.get("news_keep_days", 7),
                snapshot_keep_days=rcfg.get("scan_snapshots_keep_days", 3),
                max_snapshots_per_symbol=rcfg.get("max_snapshots_per_symbol", 30),
                earnings_window_days=self.cfg.get("earnings", {}).get("days_ahead", 7),
                vacuum=rcfg.get("vacuum_on_cleanup", True),
            )
        except Exception:
            logger.exception("Startup cleanup failed")

        await asyncio.gather(
            self.news_loop(),
            self.event_loop(),
            self.price_loop(),
            self.quick_price_loop(),
            self.india_quick_scan_loop(),  # dedicated for India focus / resilient India tab population
            self.earnings_loop(),
            self.insider_loop(),
            self.cleanup_loop(),
        )

    async def quick_price_loop(self) -> None:
        """Refresh prices for current hot list between full scans."""
        interval = self.cfg["scanner"].get("quick_price_interval_sec", 45)
        batch = self.cfg["scanner"].get("quick_price_batch", 50)

        while self._running:
            try:
                await asyncio.sleep(interval)
                async with self.state.lock:
                    syms = [x["symbol"] for x in self.state.hot[: batch * 2]]
                if not syms:
                    continue
                patches: list[dict] = []
                for i in range(0, len(syms), batch):
                    chunk = syms[i : i + batch]
                    patches.extend(await quick_refresh_symbols(chunk))
                    await asyncio.sleep(0.2)
                n = await self.state.apply_price_patches(
                    patches,
                    attempted_count=len(syms),
                )
                if n:
                    logger.info("Quick price refresh: %d hot symbols updated", n)
            except Exception:
                logger.exception("Quick price loop error")

    async def india_quick_scan_loop(self) -> None:
        """Dedicated more frequent light scan for India symbols (to make India hot tab populate faster,
        address India focus and empty India list issues). Runs separate from main price batches so
        India names get scored/inserted into state even if global hot is US dominated or scan partial.
        Uses small batches + the same engine. Skips if no India or during heavy load.
        Uses random sample each time to diversify which India names get attempted (prevents getting stuck
        only on early list items like RELIANCE.NS while others in chunk fail yf).
        """
        import random
        interval = self.cfg.get("scanner", {}).get("india_quick_interval_sec", 90)
        chunk_size = 30  # small to be resilient and not overload yf
        while self._running:
            try:
                await asyncio.sleep(interval)
                india_syms = self.state.universe.get("india", [])
                if not india_syms:
                    continue
                india_pairs, skipped_quarantined = self._eligible_pairs(
                    [(sym, "india") for sym in india_syms]
                )
                if skipped_quarantined:
                    async with self.state.lock:
                        self.state.stats["symbols_quarantined"] = skipped_quarantined
                india_syms = [sym for sym, _ in india_pairs]
                if not india_syms:
                    continue
                # random sample each cycle to hit different India names over time (diversify beyond Reliance)
                sample_size = min(chunk_size, len(india_syms))
                chunk = random.sample(india_syms, sample_size)
                async with self.state.lock:
                    earn_map = dict(self.state.earnings_by_symbol)
                    news_titles = dict(self.state.news_titles_by_symbol)
                    events_by_symbol = {
                        sym: list(events)
                        for sym, events in self.state.events_by_symbol.items()
                    }
                res = await scan_symbols(
                    chunk,
                    "india",
                    self._news_counts,
                    self.cfg.get("signals", {}).get("weights", {}),
                    earn_map,
                    news_titles,
                    events_by_symbol,
                )
                self._record_symbol_health(chunk, res)
                if res:
                    await self.state.update_scan(
                        res, self.state.hot_score_threshold or 38, partial=True
                    )
                    logger.info("India quick scan: %d symbols scored/updated (helps India tab)", len(res))
            except Exception:
                logger.exception("India quick scan loop error (non-fatal, continuing)")

    def stop(self) -> None:
        self._running = False
