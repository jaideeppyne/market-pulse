"""Quality universe fallback.

Free datacenter IPs (Render) are frequently hard-blocked by Yahoo/Stooq, so the
live price scan can return zero rows. Rather than leave Hot Movers / Top Picks
empty, we surface a curated NSE/BSE *quality universe* built purely from the
static quality-seed dataset: real company names, sectors, a fundamental grade
and multiple plain-English reasons (promoter holding, FII backing, FCF,
leadership, dividends, low debt, etc.). No network needed - always free, always
valuable. When a live price for one of these names does come through, the live
row overwrites the fallback automatically.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from app import company_names
from app.engine.research import build_research, _load as _load_quality_seed
from app.engine.sector_rules import resolve_sector

_GRADE_SCORE = {"A+": 80.0, "A": 73.0, "B": 65.0, "C": 57.0, "D": 50.0}


@lru_cache(maxsize=1)
def build_quality_universe() -> list[dict[str, Any]]:
    """Build one fundamentally-graded row per curated NSE/BSE symbol (cached)."""
    seed = _load_quality_seed()
    rows: list[dict[str, Any]] = []
    for sym in seed:
        if not sym or sym == "_DOC":
            continue
        market = "india" if sym.endswith((".NS", ".BO")) else ("uk" if sym.endswith(".L") else "us")
        name = company_names.name_for(sym) or sym
        try:
            sector = resolve_sector(sym, market)
        except Exception:
            sector = "Unknown"
        base = {"symbol": sym, "market": market, "metrics": {}}
        research = build_research(base)
        grade = research.get("grade") or "C"
        score = _GRADE_SCORE.get(grade, 55.0)
        qscore = research.get("quality_score") or score
        reasons = [r for g in research.get("groups", []) for r in g.get("reasons", [])]
        primary = (research.get("tags") or reasons or ["Quality fundamentals"])[0]
        metrics: dict[str, Any] = {
            "name": name,
            "sector": sector,
            "price": None,
            "buy_score": score,
            "quality_score": qscore,
            "factors_hit": research.get("reason_count", 0),
            "factors_total": research.get("reason_count", 0),
            "fundamental_only": True,
        }
        rows.append({
            "symbol": sym,
            "market": market,
            "name": name,
            "score": score,
            "buy_score": score,
            "quality_score": qscore,
            "metrics": metrics,
            "research": research,
            "alerts": [primary] if primary else [],
            "fundamental_only": True,
            "source": "quality_universe",
        })
    rows.sort(key=lambda r: r["buy_score"], reverse=True)
    return rows


def quality_universe_map() -> dict[str, dict[str, Any]]:
    """Symbol -> fallback row (fresh copies so callers can mutate safely)."""
    return {r["symbol"]: json.loads(json.dumps(r)) for r in build_quality_universe()}


def enabled() -> bool:
    return os.getenv("QUALITY_UNIVERSE_FALLBACK", "1") not in ("0", "false", "no")
