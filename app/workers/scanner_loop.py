from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.crawler.earnings_crawler import crawl_earnings_calendar
from app.crawler.news_crawler import crawl_news_feeds
from app.crawler.price_crawler import scan_symbols
from app.crawler.quick_prices import quick_refresh_symbols
from app.db import clear_stale_earnings, run_retention_cleanup
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

    def _all_symbols(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for sym in self.state.universe.get("us", []):
            pairs.append((sym, "us"))
        for sym in self.state.universe.get("india", []):
            pairs.append((sym, "india"))
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
                pairs = self._all_symbols()
                all_results: list[dict] = []
                batch_total = max(1, (len(pairs) + batch_size - 1) // batch_size)
                batch_index = 0
                for i in range(0, len(pairs), batch_size):
                    if not self._running:
                        break
                    chunk = pairs[i : i + batch_size]
                    batch_index += 1
                    by_market: dict[str, list[str]] = {"us": [], "india": []}
                    for sym, mkt in chunk:
                        by_market[mkt].append(sym)
                    async with self.state.lock:
                        earn_map = dict(self.state.earnings_by_symbol)
                        news_titles = dict(self.state.news_titles_by_symbol)
                    batch_results: list[dict] = []
                    for mkt, syms in by_market.items():
                        if syms:
                            res = await scan_symbols(
                                syms,
                                mkt,
                                self._news_counts,
                                weights,
                                earn_map,
                                news_titles,
                            )
                            batch_results.extend(res)
                            all_results.extend(res)
                    # Live UI update after each batch (re-sort hot list immediately)
                    await self.state.update_scan(
                        batch_results,
                        threshold,
                        partial=True,
                        batch_index=batch_index,
                        batch_total=batch_total,
                    )
                    await asyncio.sleep(delay)

                await self.state.update_scan(
                    all_results,
                    threshold,
                    partial=False,
                    batch_index=batch_total,
                    batch_total=batch_total,
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

    async def start(self) -> None:
        self._running = True
        self._universe_flat = set(self.state.universe.get("us", [])) | set(
            self.state.universe.get("india", [])
        )
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
            self.price_loop(),
            self.quick_price_loop(),
            self.earnings_loop(),
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
                n = await self.state.apply_price_patches(patches)
                if n:
                    logger.info("Quick price refresh: %d hot symbols updated", n)
            except Exception:
                logger.exception("Quick price loop error")

    def stop(self) -> None:
        self._running = False