from __future__ import annotations

from typing import Any


def sector_bucket(sector: str | None, industry: str | None, market: str) -> str:
    s = (sector or "").lower()
    i = (industry or "").lower()
    text = f"{s} {i}"
    if "bank" in text or "financial services" in s and "insurance" not in text:
        return "banks"
    if "insurance" in text or "insur" in i:
        return "insurance"
    if "real estate" in text or "reit" in text:
        return "real_estate"
    if "utility" in text or "utilities" in s:
        return "utilities"
    if "energy" in s or "oil" in i or "gas" in i:
        return "energy"
    if "technology" in s or "software" in i or "semiconductor" in i:
        return "technology"
    if "health" in s or "pharma" in i or "biotech" in i:
        return "healthcare"
    if "consumer" in s:
        return "consumer"
    if "industrial" in s or "defence" in i or "defense" in i:
        return "industrials"
    if market == "india" and any(
        x in text for x in ("defence", "defense", "ship", "aerospace", "government")
    ):
        return "india_defense_psu"
    return "general"


def pe_pb_thresholds(bucket: str, market: str) -> dict[str, float]:
    """Sector-aware valuation bands (rough defaults)."""
    base = {
        "pe_low": 5,
        "pe_high": 35,
        "pb_low": 0.5,
        "pb_high": 5.0,
        "prefer_pb_over_pe": False,
    }
    overrides = {
        "banks": {"pe_low": 4, "pe_high": 18, "pb_low": 0.6, "pb_high": 3.5, "prefer_pb_over_pe": True},
        "insurance": {"pe_low": 6, "pe_high": 22, "prefer_pb_over_pe": True},
        "real_estate": {"pe_high": 30, "pb_high": 4, "prefer_pb_over_pe": True},
        "technology": {"pe_high": 55, "pb_high": 12, "prefer_pb_over_pe": False},
        "healthcare": {"pe_high": 45, "prefer_pb_over_pe": False},
        "utilities": {"pe_high": 22, "dividend_focus": True},
        "energy": {"pe_high": 15, "pb_high": 2.5},
        "india_defense_psu": {"pe_high": 50, "pb_high": 8},
    }
    out = dict(base)
    out.update(overrides.get(bucket, {}))
    if market == "india":
        out["pe_high"] = out.get("pe_high", 35) * 1.15
    return out