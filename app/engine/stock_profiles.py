"""Curated, durable stock intelligence (business, risks, valuation, peers).

Qualitative only — no live numbers — so it never goes stale or misleads. Names
without a hand-written profile get a sensible sector-based fallback so the UI
always shows a balanced research note (bull case + what-to-watch), not just a
one-sided 'good stock' pitch.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_PATH = Path(os.getenv("STOCK_PROFILES_PATH", _ROOT / "data" / "stock_profiles.json"))
_profiles: dict[str, dict] = {}
_loaded = False

# Sector-level fallback intelligence (archetype + generic watch-outs) so even
# uncovered names get a useful, honest balanced note.
_SECTOR_FALLBACK: dict[str, dict] = {
    "Technology": {"archetype": "IT services — cyclical to global tech budgets",
        "watch": ["Earnings track US/Europe IT spending — a recession there slows deals", "AI could pressure the headcount-led billing model", "Rupee/dollar moves swing margins"]},
    "Financial Services": {"archetype": "Lender — credit-cycle sensitive",
        "watch": ["Asset quality (bad loans) rises in a slowdown", "Margins compress when interest rates fall", "Regulation can change the rules quickly"]},
    "Consumer Defensive": {"archetype": "Defensive FMCG",
        "watch": ["Rural demand and raw-material costs swing volumes/margins", "Usually richly valued for steady single/double-digit growth", "Smaller local brands chip at share"]},
    "Consumer Cyclical": {"archetype": "Discretionary — demand-cycle sensitive",
        "watch": ["Big-ticket/discretionary spend slows in downturns", "Input-cost inflation pressures margins", "Competitive intensity"]},
    "Healthcare": {"archetype": "Pharma — regulation & pricing sensitive",
        "watch": ["US FDA plant inspections can hit specific facilities", "US generic pricing is deflationary", "R&D/specialty bets are long-dated"]},
    "Energy": {"archetype": "Energy — commodity-cyclical",
        "watch": ["Earnings swing with global crude/commodity prices", "Heavy capex cycles", "Energy-transition / policy overhang"]},
    "Basic Materials": {"archetype": "Materials — cyclical",
        "watch": ["Prices/demand are cyclical and regional", "Energy & raw-material costs swing margins", "New capacity can pressure prices"]},
    "Industrials": {"archetype": "Capex/infra cyclical",
        "watch": ["Order inflow and execution drive lumpy earnings", "Working-capital heavy", "Government/order-book dependence"]},
    "Utilities": {"archetype": "Regulated utility — defensive",
        "watch": ["Regulated returns cap upside", "Capex execution risk", "Energy-transition exposure"]},
    "Communication Services": {"archetype": "Telecom/media",
        "watch": ["Heavy capex and competitive pricing", "Regulatory/spectrum costs", "Subscriber/ARPU trends drive value"]},
}


def _load() -> dict[str, dict]:
    global _loaded, _profiles
    if _loaded:
        return _profiles
    try:
        raw = json.loads(_PATH.read_text(encoding="utf-8"))
        _profiles = {k.upper(): v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)}
    except Exception:
        _profiles = {}
    _loaded = True
    return _profiles


def profile_for(symbol: str, sector: str | None = None) -> dict[str, Any] | None:
    """Return the curated profile for a symbol, or a sector-based fallback."""
    if not symbol:
        return None
    p = _load().get(symbol.upper())
    if p:
        return {**p, "_curated": True}
    fb = _SECTOR_FALLBACK.get(sector or "")
    if fb:
        return {"archetype": fb["archetype"], "watch": list(fb["watch"]), "_curated": False}
    return None
