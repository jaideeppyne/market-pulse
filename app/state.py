from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.engine.sector_intel import build_cycle_overview, build_sector_summary


@dataclass
class AppState:
    """Thread-safe shared state for scanners and WebSocket clients."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    universe: dict[str, list[str]] = field(default_factory=dict)
    symbols: dict[str, dict[str, Any]] = field(default_factory=dict)
    hot: list[dict[str, Any]] = field(default_factory=list)
    hot_by_market: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    sectors: list[dict[str, Any]] = field(default_factory=list)
    cycle_overview: list[dict[str, Any]] = field(default_factory=list)
    news: list[dict[str, Any]] = field(default_factory=list)
    news_by_symbol: dict[str, int] = field(default_factory=dict)
    news_titles_by_symbol: dict[str, list[str]] = field(default_factory=dict)
    earnings: list[dict[str, Any]] = field(default_factory=list)
    earnings_by_symbol: dict[str, dict[str, Any]] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    hot_top_n: int = 200
    hot_score_threshold: float = 55.0
    scan_generation: int = 0
    live_tick: int = 0
    broadcast_event: asyncio.Event = field(default_factory=asyncio.Event)

    @staticmethod
    def _slim_scan_row(row: dict[str, Any]) -> dict[str, Any]:
        """Light payload for WebSocket (full factor_breakdown via /api/symbol)."""
        m = dict(row.get("metrics") or {})
        for key in ("factor_breakdown", "signals", "factors_by_category"):
            m.pop(key, None)
        return {
            "symbol": row.get("symbol"),
            "market": row.get("market"),
            "score": row.get("score"),
            "factors_hit": row.get("factors_hit"),
            "factors_total": row.get("factors_total"),
            "alerts": (row.get("alerts") or [])[:6],
            "metrics": m,
            "sparkline": row.get("sparkline"),
            "top_factors": (m.get("top_weighted_factors") or [])[:10],
        }

    def _rebuild_hot_lists(self) -> None:
        threshold = self.hot_score_threshold
        top_n = self.hot_top_n
        all_items = sorted(
            self.symbols.values(),
            key=lambda x: x.get("score", 0),
            reverse=True,
        )
        hot_all = [x for x in all_items if x.get("score", 0) >= threshold]
        self.hot = hot_all[:top_n]
        us = [x for x in all_items if x.get("market") == "us" and x.get("score", 0) >= threshold]
        india = [
            x
            for x in all_items
            if x.get("market") == "india" and x.get("score", 0) >= threshold
        ]
        self.hot_by_market = {
            "us": us[:top_n],
            "india": india[:top_n],
        }
        self.sectors = build_sector_summary(
            self.symbols, hot_threshold=threshold
        )
        self.cycle_overview = build_cycle_overview(self.sectors)

    async def update_scan(
        self,
        results: list[dict[str, Any]],
        threshold: float,
        *,
        partial: bool = False,
        batch_index: int = 0,
        batch_total: int = 0,
    ) -> None:
        async with self.lock:
            self.hot_score_threshold = threshold
            for r in results:
                self.symbols[r["symbol"]] = r
            self._rebuild_hot_lists()
            now = datetime.now(timezone.utc).isoformat()
            self.scan_generation += 1
            self.live_tick += 1
            self.stats.update(
                {
                    "symbols_tracked": len(self.symbols),
                    "hot_count": len(
                        [x for x in self.symbols.values() if x.get("score", 0) >= threshold]
                    ),
                    "hot_shown": len(self.hot),
                    "sector_count": len(self.sectors),
                    "last_price_tick": now,
                    "scan_in_progress": partial,
                    "scan_batch": batch_index,
                    "scan_batches_total": batch_total,
                    "scan_generation": self.scan_generation,
                    "live_tick": self.live_tick,
                }
            )
            if not partial:
                self.stats["last_price_scan"] = now
                self.stats["scan_in_progress"] = False
        self.broadcast_event.set()

    async def apply_price_patches(self, patches: list[dict[str, Any]]) -> int:
        """Update live prices on hot symbols without full factor re-scan."""
        if not patches:
            return 0
        updated = 0
        async with self.lock:
            for p in patches:
                sym = p.get("symbol")
                if not sym or sym not in self.symbols:
                    continue
                row = self.symbols[sym]
                m = row.setdefault("metrics", {})
                if "price" in p:
                    m["price"] = p["price"]
                if "day_chg_pct" in p:
                    m["day_chg_pct"] = p["day_chg_pct"]
                if "ret5d_pct" in p:
                    m["ret5d_pct"] = p["ret5d_pct"]
                if p.get("sparkline"):
                    row["sparkline"] = p["sparkline"]
                updated += 1
            if updated:
                self._rebuild_hot_lists()
                self.scan_generation += 1
                now = datetime.now(timezone.utc).isoformat()
                self.live_tick += 1
                self.stats.update(
                    {
                        "last_price_tick": now,
                        "scan_generation": self.scan_generation,
                        "live_tick": self.live_tick,
                        "hot_shown": len(self.hot),
                        "last_quick_price": now,
                    }
                )
        if updated:
            self.broadcast_event.set()
        return updated

    async def update_news(
        self,
        items: list[dict[str, Any]],
        counts: dict[str, int],
        titles: dict[str, list[str]] | None = None,
    ) -> None:
        async with self.lock:
            self.news = items[:150]
            for k, v in (counts or {}).items():
                self.news_by_symbol[k] = self.news_by_symbol.get(k, 0) + v
            if titles:
                for sym, new_titles in titles.items():
                    merged = (new_titles + self.news_titles_by_symbol.get(sym, []))[:40]
                    self.news_titles_by_symbol[sym] = merged
            self.stats["last_news_scan"] = datetime.now(timezone.utc).isoformat()
            self.stats["news_count"] = len(self.news)
            self.live_tick += 1
            self.stats["live_tick"] = self.live_tick
        self.broadcast_event.set()

    async def update_earnings(self, items: list[dict[str, Any]]) -> None:
        async with self.lock:
            enriched = []
            for e in items:
                row = dict(e)
                scan = self.symbols.get(e["symbol"], {})
                row["score"] = scan.get("score")
                m = scan.get("metrics") or {}
                row["rsi"] = m.get("rsi")
                row["day_chg_pct"] = m.get("day_chg_pct")
                row["name"] = m.get("name", e["symbol"])
                enriched.append(row)
            enriched.sort(key=lambda x: (x.get("days_until", 99), -(x.get("score") or 0)))
            self.earnings = enriched
            self.earnings_by_symbol = {e["symbol"]: e for e in enriched}
            self.stats["earnings_upcoming"] = len(enriched)
            self.stats["last_earnings_scan"] = datetime.now(timezone.utc).isoformat()
        self.broadcast_event.set()

    async def snapshot(self, *, light: bool = False) -> dict[str, Any]:
        async with self.lock:
            top_n = self.hot_top_n
            hot = list(self.hot[:top_n])
            hot_bm = {k: list(v[:top_n]) for k, v in self.hot_by_market.items()}
            if light:
                hot = [self._slim_scan_row(r) for r in hot]
                hot_bm = {k: [self._slim_scan_row(r) for r in v] for k, v in hot_bm.items()}
            # Augment calendar earnings with symbols that have strong recent "earnings" buzz in news
            # (helps the list feel less sparse when yf calendars only have a few entries for the window)
            buzz = []
            seen = {e["symbol"] for e in self.earnings}
            earn_kw = re.compile(r"earn|result|beat|guidance|q[1-4]", re.I)
            for n in self.news[:80]:
                if earn_kw.search(n.get("title", "")) or "earnings" in (n.get("title", "") + " ".join(n.get("symbols", []))).lower():
                    for s in (n.get("symbols") or []):
                        if s not in seen:
                            seen.add(s)
                            buzz.append({
                                "symbol": s,
                                "market": "us" if not s.endswith(".NS") else "india",
                                "earnings_date": "news",
                                "days_until": None,
                                "eps_avg": None,
                                "score": (self.symbols.get(s) or {}).get("score"),
                                "name": ( (self.symbols.get(s) or {}).get("metrics") or {} ).get("name", s),
                                "day_chg_pct": ( (self.symbols.get(s) or {}).get("metrics") or {} ).get("day_chg_pct"),
                                "from_news": True,
                                "news_title": n.get("title", "")[:80],
                            })
            aug_earnings = list(self.earnings[:80]) + buzz[:20]  # cap the buzz add-ons

            return {
                "started_at": self.started_at,
                "stats": dict(self.stats),
                "hot": hot,
                "hot_by_market": hot_bm,
                "earnings": aug_earnings,
                "news": list(self.news[:60]),
                "universe_sizes": {k: len(v) for k, v in self.universe.items()},
                "sectors": list(self.sectors),
                "cycle_overview": list(self.cycle_overview),
                "scan_generation": self.scan_generation,
                "live_tick": self.live_tick,
            }