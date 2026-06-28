from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from app.engine.sector_intel import build_cycle_overview, build_sector_summary


def _ensure_event_loop() -> None:
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def _new_lock() -> asyncio.Lock:
    _ensure_event_loop()
    return asyncio.Lock()


def _new_event() -> asyncio.Event:
    _ensure_event_loop()
    return asyncio.Event()


@dataclass
class AppState:
    """Thread-safe shared state for scanners and WebSocket clients."""

    lock: asyncio.Lock = field(default_factory=_new_lock)
    universe: dict[str, list[str]] = field(default_factory=dict)
    symbols: dict[str, dict[str, Any]] = field(default_factory=dict)
    hot: list[dict[str, Any]] = field(default_factory=list)
    hot_by_market: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    sectors: list[dict[str, Any]] = field(default_factory=list)
    cycle_overview: list[dict[str, Any]] = field(default_factory=list)
    news: list[dict[str, Any]] = field(default_factory=list)
    news_by_symbol: dict[str, int] = field(default_factory=dict)
    news_titles_by_symbol: dict[str, list[str]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    events_by_symbol: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    earnings: list[dict[str, Any]] = field(default_factory=list)
    earnings_by_symbol: dict[str, dict[str, Any]] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)
    # Persisted watchlist + alerts (loaded from DB on demand / startup; augmented in snapshot)
    watches: list[dict[str, Any]] = field(default_factory=list)
    recent_server_alerts: list[dict[str, Any]] = field(default_factory=list)  # latest triggered for WS push convenience
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    hot_top_n: int = 200
    hot_score_threshold: float = 55.0
    scan_generation: int = 0
    live_tick: int = 0
    broadcast_event: asyncio.Event = field(default_factory=_new_event)
    jobs: dict = field(default_factory=dict)  # job_id -> {"status": "running"/"done"/"error", "progress": 0-100, "result": ..., "started": ...}
    investor_events: list = field(default_factory=list)  # recent official filings (insider/ceo/promoter etc.) for UI/radar

    @staticmethod
    def _buy_rank(row: dict[str, Any]) -> float:
        """Ranking score for live scanner views; prefer explicit buy_score."""
        m = row.get("metrics") or {}
        value = row.get("buy_score")
        if value is None:
            value = m.get("buy_score")
        if value is None:
            value = row.get("score", 0)
        try:
            return float(value or 0)
        except Exception:
            return 0.0

    @staticmethod
    def _slim_scan_row(row: dict[str, Any]) -> dict[str, Any]:
        """Light payload for WebSocket (full factor_breakdown via /api/symbol)."""
        m = dict(row.get("metrics") or {})
        for key in ("factor_breakdown", "signals", "factors_by_category"):
            m.pop(key, None)
        buy_score = row.get("buy_score", m.get("buy_score", row.get("score")))
        quality_score = row.get("quality_score", m.get("quality_score"))
        _res = row.get("research") or {}
        if _res:
            # keep a light but useful research view for the homepage hero:
            # grade/tags + a capped set of grouped reasons (small strings)
            _groups = []
            for _g in (_res.get("groups") or [])[:5]:
                _rs = [str(x) for x in (_g.get("reasons") or [])[:3]]
                if _rs:
                    _groups.append({"title": _g.get("title"), "reasons": _rs})
            research = {
                "grade": _res.get("grade"),
                "quality_score": _res.get("quality_score"),
                "fundamentally_strong": _res.get("fundamentally_strong"),
                "tags": (_res.get("tags") or [])[:4],
                "reason_count": _res.get("reason_count"),
                "groups": _groups,
                "summary": _res.get("summary"),
            }
        else:
            research = None
        return {
            "symbol": row.get("symbol"),
            "market": row.get("market"),
            "score": row.get("score"),
            "buy_score": buy_score,
            "quality_score": quality_score,
            "factors_hit": row.get("factors_hit"),
            "factors_total": row.get("factors_total"),
            "alerts": (row.get("alerts") or [])[:6],
            "metrics": m,
            "sparkline": row.get("sparkline"),
            "top_factors": (m.get("top_weighted_factors") or [])[:10],
            "research": research,
        }

    def _rebuild_hot_lists(self) -> None:
        threshold = self.hot_score_threshold
        top_n = self.hot_top_n
        all_items = sorted(
            self.symbols.values(),
            key=self._buy_rank,
            reverse=True,
        )
        hot_all = [x for x in all_items if self._buy_rank(x) >= threshold]
        self.hot = hot_all[:top_n]
        # Global hot stays strict (names >= threshold, top N overall for the "Hot" stat and main view).
        # For market tabs (India / US), ALWAYS surface the top scored for that market (top 50 by score,
        # no or minimal threshold). This ensures the India tab in Hot Movers is never empty when there
        # are any processed India names (addresses "still India list empty" even if global hot is US-heavy
        # or small during partial scans). Uses recent scores from the live state.
        all_us = [x for x in all_items if x.get("market") == "us"]
        all_india = [x for x in all_items if x.get("market") == "india"]
        all_uk = [x for x in all_items if x.get("market") == "uk"]
        all_us.sort(key=self._buy_rank, reverse=True)
        all_india.sort(key=self._buy_rank, reverse=True)
        all_uk.sort(key=self._buy_rank, reverse=True)
        # Apply a reasonable floor for market tabs too (prevents low-conviction 'weak setup' stocks from polluting the list).
        # Keeps India tab useful without showing nonsense low-edge names. Global hot is stricter.
        tab_threshold = max(threshold * 0.6, 15)
        all_us = [x for x in all_us if self._buy_rank(x) >= tab_threshold]
        all_india = [x for x in all_india if self._buy_rank(x) >= tab_threshold]
        all_uk = [x for x in all_uk if self._buy_rank(x) >= tab_threshold]
        self.hot_by_market = {
            "us": all_us[:50],
            "india": all_india[:50],
            "uk": all_uk[:50],
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
        attempted_count: int | None = None,
    ) -> None:
        async with self.lock:
            self.hot_score_threshold = threshold
            for r in results:
                self.symbols[r["symbol"]] = r
            # Bound the in-memory symbol cache so it can't grow without limit and
            # OOM the free 512MB instance. Keep the highest-ranked names (what the
            # UI actually surfaces); dropped ones simply re-fetch on demand.
            _CAP = 1000
            if len(self.symbols) > _CAP:
                kept = sorted(self.symbols.items(), key=lambda kv: self._buy_rank(kv[1]), reverse=True)[:_CAP]
                self.symbols = dict(kept)
            self._rebuild_hot_lists()
            now = datetime.now(timezone.utc).isoformat()
            self.scan_generation += 1
            self.live_tick += 1
            stats_update = {
                "symbols_tracked": len(self.symbols),
                "hot_count": len(
                    [x for x in self.symbols.values() if self._buy_rank(x) >= threshold]
                ),
                "hot_shown": len(self.hot),
                "sector_count": len(self.sectors),
                "last_price_tick": now,
                "scan_in_progress": partial,
                "scan_batch": batch_index,
                "scan_batches_total": batch_total,
                "scan_generation": self.scan_generation,
                "live_tick": self.live_tick,
                "last_price_batch_result_count": len(results),
                "last_price_batch_empty": partial and len(results) == 0,
            }
            if attempted_count is not None:
                stats_update["last_price_batch_attempted"] = attempted_count
            self.stats.update(stats_update)
            if not partial:
                self.stats["last_price_scan"] = now
                self.stats["scan_in_progress"] = False
                self.stats["last_full_price_scan_result_count"] = len(results)
                self.stats["last_full_price_scan_empty"] = len(results) == 0
                if attempted_count is not None:
                    self.stats["last_full_price_scan_attempted"] = attempted_count
                if len(results) == 0:
                    self.stats["last_empty_price_scan"] = now
        self.broadcast_event.set()

    async def apply_price_patches(
        self,
        patches: list[dict[str, Any]],
        *,
        attempted_count: int | None = None,
    ) -> int:
        """Update live prices on hot symbols without full factor re-scan."""
        patch_count = len(patches or [])
        if not patch_count and attempted_count is None:
            return 0
        updated = 0
        async with self.lock:
            for p in patches or []:
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
            stats_update = {
                "last_quick_price": now,
                "last_quick_price_patch_count": patch_count,
                "last_quick_price_updated_count": updated,
                "last_quick_price_empty": updated == 0,
                "live_tick": self.live_tick,
            }
            if attempted_count is not None:
                stats_update["last_quick_price_attempted"] = attempted_count
            if updated:
                stats_update.update(
                    {
                        "last_price_tick": now,
                        "scan_generation": self.scan_generation,
                        "hot_shown": len(self.hot),
                    }
                )
            else:
                stats_update["last_empty_quick_price"] = now
            self.stats.update(stats_update)
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
            now = datetime.now(timezone.utc).isoformat()
            result_count = len(items or [])
            self.stats["last_news_scan"] = now
            self.stats["news_count"] = len(self.news)
            self.stats["last_news_scan_result_count"] = result_count
            self.stats["last_news_scan_symbol_count"] = len(counts or {})
            self.stats["last_news_scan_empty"] = result_count == 0
            if result_count == 0:
                self.stats["last_empty_news_scan"] = now
            self.live_tick += 1
            self.stats["live_tick"] = self.live_tick
        self.broadcast_event.set()

    async def update_events(self, events: list[dict[str, Any]]) -> None:
        async with self.lock:
            result_count = len(events or [])
            if events:
                merged = events + self.events
                seen = set()
                deduped = []
                for e in merged:
                    key = e.get("event_key") or f"{e.get('symbol')}:{e.get('event_type')}:{e.get('title')}"
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped.append(e)
                self.events = deduped[:250]
                by_symbol: dict[str, list[dict[str, Any]]] = {}
                for e in self.events:
                    sym = e.get("symbol")
                    if sym:
                        by_symbol.setdefault(sym, []).append(e)
                self.events_by_symbol = {k: v[:20] for k, v in by_symbol.items()}
            now = datetime.now(timezone.utc).isoformat()
            self.stats["market_events_count"] = len(self.events)
            self.stats["last_event_scan"] = now
            self.stats["last_event_scan_result_count"] = result_count
            self.stats["last_event_scan_empty"] = result_count == 0
            if result_count == 0:
                self.stats["last_empty_event_scan"] = now
            self.live_tick += 1
            self.stats["live_tick"] = self.live_tick
        self.broadcast_event.set()

    async def update_candidates(self, candidates: list[dict[str, Any]]) -> None:
        async with self.lock:
            self.candidates = candidates[:300]
            result_count = len(candidates or [])
            now = datetime.now(timezone.utc).isoformat()
            self.stats["candidate_count"] = len(self.candidates)
            self.stats["last_light_scan"] = now
            self.stats["last_light_scan_result_count"] = result_count
            self.stats["last_light_scan_empty"] = result_count == 0
            if result_count == 0:
                self.stats["last_empty_light_scan"] = now
            self.live_tick += 1
            self.stats["live_tick"] = self.live_tick
        self.broadcast_event.set()

    async def update_earnings(self, items: list[dict[str, Any]]) -> None:
        async with self.lock:
            result_count = len(items or [])
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
            # Merge news-driven earnings buzz directly into the main list.
            # This is critical for Indian companies: yf calendars are sparse, but news (from multiple India feeds)
            # frequently mentions "results", "Q1 results", "to announce earnings" etc.
            # By merging here, the earnings section gets many more items (not just the 2 from yf).
            buzz = self._generate_earnings_buzz()
            seen = {e["symbol"] for e in enriched}
            for b in buzz:
                if b.get("symbol") not in seen:
                    enriched.append(b)
            enriched.sort(key=lambda x: (x.get("days_until", 99) or 99, -(x.get("score") or 0)))
            self.earnings = enriched[:120]
            self.earnings_by_symbol = {e["symbol"]: e for e in self.earnings}
            now = datetime.now(timezone.utc).isoformat()
            self.stats["earnings_upcoming"] = len(self.earnings)
            self.stats["last_earnings_scan"] = now
            self.stats["last_earnings_scan_result_count"] = result_count
            self.stats["last_earnings_scan_empty"] = result_count == 0
            if result_count == 0:
                self.stats["last_empty_earnings_scan"] = now
        self.broadcast_event.set()

    def _generate_earnings_buzz(self) -> list[dict[str, Any]]:
        """Aggressive news-based earnings detection.
        Scans recent news (populated by multi-website RSS + Google News including new India earnings feeds)
        for any mention of results/earnings/Qx for tagged symbols.
        Creates 'from_news' entries so Indian companies show up even when yf has no calendar data.
        Includes simple date parsing for titles containing 'on 15 Jul' etc.
        """
        buzz = []
        seen = set()
        # Very broad to catch Indian media phrasing: "results", "Q1 results", "earnings", "declare results", "to announce"
        earn_kw = re.compile(r"result|earn|q[1-4]|declare|announce|guidance|beat|to report|earnings today|results today", re.I)
        date_re = re.compile(r"(?:on|results?\s*(?:on|date|scheduled for)?)\s*(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|July|June)?|(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", re.I)
        today = datetime.now(timezone.utc).date()
        for n in (self.news or [])[:200]:
            title = n.get("title") or ""
            title_lower = title.lower()
            if not earn_kw.search(title) and "result" not in title_lower and "q1" not in title_lower and "q2" not in title_lower:
                continue
            for s in (n.get("symbols") or []):
                if s in seen:
                    continue
                seen.add(s)
                days_until = None
                ed_str = "news"
                m = date_re.search(title)
                if m:
                    try:
                        day = int(m.group(1) or m.group(3))
                        mon_str = (m.group(2) or m.group(4) or "").lower()[:3]
                        mon_map = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
                        mon = mon_map.get(mon_str, today.month)
                        ed = date(today.year, mon, min(max(day,1),28))
                        if ed < today:
                            ed = date(today.year + (1 if mon <= today.month else 0), mon, min(max(day,1),28))
                        days_until = (ed - today).days
                        ed_str = ed.isoformat()
                    except Exception:
                        pass
                is_india = bool(s.endswith(".NS") or s.endswith(".BO"))
                buzz_item = {
                    "symbol": s,
                    "market": "india" if is_india else "uk" if s.endswith(".L") else "us",
                    "earnings_date": ed_str,
                    "days_until": days_until,
                    "eps_avg": None,
                    "score": (self.symbols.get(s) or {}).get("score"),
                    "name": ((self.symbols.get(s) or {}).get("metrics") or {}).get("name", s),
                    "day_chg_pct": ((self.symbols.get(s) or {}).get("metrics") or {}).get("day_chg_pct"),
                    "from_news": True,
                    "news_title": title[:95],
                }
                buzz.append(buzz_item)
        # Strongly favor Indian items so .NS companies appear
        india = [b for b in buzz if b["market"] == "india"]
        other = [b for b in buzz if b["market"] != "india"]
        return india[:50] + other[:20]

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
            # Next-level: better India support + simple date extraction from titles for "results on 12 Jul" etc.
            buzz = []
            seen = {e["symbol"] for e in self.earnings}
            # Broad keywords + India specific ("results", "Q1", "to announce", "declare results")
            earn_kw = re.compile(r"earn|result|beat|guidance|q[1-4]|declare|announce|to report", re.I)
            # Simple date extractor for news titles (supports India "15 Jul", "July 12", "on 12th")
            date_re = re.compile(r"(?:on|results?\s*(?:on|date)?)\s*(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|July|June|Sept)?|(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", re.I)
            today = datetime.now(timezone.utc).date()
            for n in self.news[:120]:  # more news for better coverage
                title = n.get("title", "")
                if earn_kw.search(title) or any(k in title.lower() for k in ["earnings", "results", "q1", "q2", "q3", "q4"]):
                    for s in (n.get("symbols") or []):
                        if s not in seen:
                            seen.add(s)
                            # Try to parse a date for better "upcoming" display
                            days_until = None
                            ed_str = "news"
                            m = date_re.search(title)
                            if m:
                                try:
                                    day = int(m.group(1) or m.group(3))
                                    mon_str = (m.group(2) or m.group(4) or "").lower()[:3]
                                    mon_map = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
                                    mon = mon_map.get(mon_str, today.month)
                                    # Assume current or next month if past
                                    ed = date(today.year, mon, min(day, 28))
                                    if ed < today:
                                        ed = date(today.year + (1 if mon < today.month else 0), mon, min(day,28))
                                    days_until = (ed - today).days
                                    ed_str = ed.isoformat()
                                except:
                                    pass
                            is_india = s.endswith(".NS")
                            buzz.append({
                                "symbol": s,
                                "market": "india" if is_india else "uk" if s.endswith(".L") else "us",
                                "earnings_date": ed_str,
                                "days_until": days_until,
                                "eps_avg": None,
                                "score": (self.symbols.get(s) or {}).get("score"),
                                "name": ( (self.symbols.get(s) or {}).get("metrics") or {} ).get("name", s),
                                "day_chg_pct": ( (self.symbols.get(s) or {}).get("metrics") or {} ).get("day_chg_pct"),
                                "from_news": True,
                                "news_title": title[:90],
                            })
            # More buzz for India (to compensate for weaker yf calendar coverage on .NS)
            india_buzz = [b for b in buzz if b["market"] == "india"]
            us_buzz = [b for b in buzz if b["market"] == "us"]
            aug_earnings = list(self.earnings[:60]) + india_buzz[:30] + us_buzz[:15]

            return {
                "started_at": self.started_at,
                "stats": dict(self.stats),
                "hot": hot,
                "hot_by_market": hot_bm,
                "earnings": aug_earnings,
                "events": list(self.events[:80]),
                "candidates": list(self.candidates[:120]),
                "investor_events": list(getattr(self, "investor_events", [])[-20:]),  # recent official filings (insider/ceo/promoter etc.) for UI/radar
                "news": list(self.news[:60]),
                "universe_sizes": {k: len(v) for k, v in self.universe.items()},
                "sectors": list(self.sectors),
                "cycle_overview": list(self.cycle_overview),
                "scan_generation": self.scan_generation,
                "live_tick": self.live_tick,
                # Server watch + alerts for multi-device + restart safety (populated by main endpoints / eval)
                "watches": list(getattr(self, "watches", []) or []),
                "alerts": list(getattr(self, "recent_server_alerts", [])[-30:]),
            }
