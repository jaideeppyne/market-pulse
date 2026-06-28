"""Sector aggregation, cyclical tags, and rotation signals for the UI."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.engine.sector_rules import sector_bucket

# Yahoo-style sector → cyclical / defensive / growth label
CYCLICAL_PROFILE: dict[str, dict[str, str]] = {
    "technology": {"cycle": "growth", "label": "Growth / innovation"},
    "financial services": {"cycle": "cyclical", "label": "Cyclical · rate-sensitive"},
    "consumer cyclical": {"cycle": "cyclical", "label": "Cyclical · discretionary"},
    "consumer defensive": {"cycle": "defensive", "label": "Defensive · staples"},
    "healthcare": {"cycle": "defensive", "label": "Defensive · healthcare"},
    "utilities": {"cycle": "defensive", "label": "Defensive · utilities"},
    "energy": {"cycle": "cyclical", "label": "Cyclical · commodities"},
    "basic materials": {"cycle": "cyclical", "label": "Cyclical · materials"},
    "industrials": {"cycle": "cyclical", "label": "Cyclical · capex"},
    "communication services": {"cycle": "growth", "label": "Growth · comms"},
    "real estate": {"cycle": "cyclical", "label": "Cyclical · REITs"},
    "unknown": {"cycle": "mixed", "label": "Mixed / unclassified"},
}

BUCKET_CYCLE: dict[str, str] = {
    "banks": "cyclical",
    "insurance": "cyclical",
    "technology": "growth",
    "healthcare": "defensive",
    "utilities": "defensive",
    "energy": "cyclical",
    "consumer": "cyclical",
    "industrials": "cyclical",
    "india_defense_psu": "thematic",
    "real_estate": "cyclical",
    "general": "mixed",
}


def _cyclical_meta(sector_name: str, bucket: str) -> dict[str, str]:
    key = (sector_name or "unknown").lower().strip()
    prof = CYCLICAL_PROFILE.get(key)
    if prof:
        return prof
    cycle = BUCKET_CYCLE.get(bucket, "mixed")
    labels = {
        "cyclical": "Cyclical sector",
        "defensive": "Defensive sector",
        "growth": "Growth sector",
        "thematic": "Thematic (India policy/PSU)",
        "mixed": "Mixed cyclicality",
    }
    return {"cycle": cycle, "label": labels.get(cycle, "Mixed")}


def _slim_pick(row: dict[str, Any]) -> dict[str, Any]:
    m = row.get("metrics") or {}
    res = row.get("research") or {}
    return {
        "symbol": row.get("symbol"),
        "market": row.get("market"),
        "score": row.get("score"),
        "buy_score": m.get("buy_score", row.get("score")),
        "quality_score": m.get("quality_score"),
        "factors_hit": row.get("factors_hit"),
        "factors_total": row.get("factors_total"),
        "day_chg_pct": m.get("day_chg_pct"),
        "price": m.get("price"),
        "name": m.get("name"),
        "is_extended": m.get("is_extended"),
        "sector_bucket": m.get("sector_bucket"),
        "pct_52w_range": m.get("pct_52w_range"),
        "grade": res.get("grade"),
        "archetype": res.get("archetype"),
        "fundamentally_strong": res.get("fundamentally_strong"),
        "tags": (res.get("tags") or [])[:2],
    }


def _rotation_signal(avg_day: float, avg_buy: float, hot_ratio: float) -> str:
    if avg_day >= 0.8 and avg_buy >= 52:
        return "leading"
    if avg_day <= -0.5 and avg_buy < 45:
        return "lagging"
    if hot_ratio >= 0.35 and avg_buy >= 48:
        return "warming"
    return "neutral"


def build_sector_summary(
    symbols: dict[str, dict[str, Any]],
    *,
    hot_threshold: float = 38.0,
    top_picks_per_sector: int = 10,
) -> list[dict[str, Any]]:
    by_sector: dict[str, list[dict]] = defaultdict(list)
    for row in symbols.values():
        m = row.get("metrics") or {}
        name = (m.get("sector") or "Unknown").strip() or "Unknown"
        by_sector[name].append(row)

    sectors_out: list[dict[str, Any]] = []
    for sector_name, stocks in by_sector.items():
        if not stocks:
            continue
        buckets = [
            (s.get("metrics") or {}).get("sector_bucket")
            or sector_bucket(
                sector_name,
                (s.get("metrics") or {}).get("industry"),
                s.get("market", "us"),
            )
            for s in stocks
        ]
        bucket = max(set(buckets), key=buckets.count)
        cyclical = _cyclical_meta(sector_name, bucket)

        buy_scores = [
            (s.get("metrics") or {}).get("buy_score") or s.get("score") or 0
            for s in stocks
        ]
        day_chgs = [(s.get("metrics") or {}).get("day_chg_pct") or 0 for s in stocks]
        hot = [s for s in stocks if (s.get("score") or 0) >= hot_threshold]
        early_buys = [
            s
            for s in stocks
            if (s.get("score") or 0) >= hot_threshold
            and not (s.get("metrics") or {}).get("is_extended")
        ]
        extended = sum(1 for s in stocks if (s.get("metrics") or {}).get("is_extended"))

        def _buy_key(x: dict) -> float:
            return float(
                (x.get("metrics") or {}).get("buy_score") or x.get("score") or 0
            )

        ranked = sorted(stocks, key=_buy_key, reverse=True)
        early_syms = {s.get("symbol") for s in early_buys}
        hot_syms = {s.get("symbol") for s in hot}
        picks = [
            s
            for s in ranked
            if s.get("symbol") in early_syms
            or s.get("symbol") in hot_syms
            or _buy_key(s) >= hot_threshold - 5
        ][:top_picks_per_sector]
        if len(picks) < min(5, len(ranked)):
            picks = ranked[: min(max(top_picks_per_sector, 5), len(ranked))]

        avg_buy = sum(buy_scores) / len(buy_scores) if buy_scores else 0
        avg_day = sum(day_chgs) / len(day_chgs) if day_chgs else 0
        hot_ratio = len(hot) / len(stocks) if stocks else 0

        sectors_out.append(
            {
                "sector": sector_name,
                "sector_bucket": bucket,
                "cycle": cyclical["cycle"],
                "cycle_label": cyclical["label"],
                "stock_count": len(stocks),
                "hot_count": len(hot),
                "early_buy_count": len(early_buys),
                "extended_count": extended,
                "avg_buy_score": round(avg_buy, 1),
                "avg_day_chg_pct": round(avg_day, 2),
                "avg_quality_score": round(
                    sum(
                        (s.get("metrics") or {}).get("quality_score") or 0
                        for s in stocks
                    )
                    / len(stocks),
                    1,
                ),
                "rotation": _rotation_signal(avg_day, avg_buy, hot_ratio),
                "top_picks": [_slim_pick(p) for p in picks],
                "stocks": [_slim_pick(p) for p in ranked],
                "us_count": sum(1 for s in stocks if s.get("market") == "us"),
                "india_count": sum(1 for s in stocks if s.get("market") == "india"),
            }
        )

    sectors_out.sort(
        key=lambda x: (x["early_buy_count"], x["avg_buy_score"], x["hot_count"]),
        reverse=True,
    )
    return sectors_out


def build_cycle_overview(sectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Roll up sector rows into cyclical groups for the dashboard strip."""
    groups: dict[str, dict] = defaultdict(
        lambda: {
            "cycle": "",
            "stock_count": 0,
            "hot_count": 0,
            "early_buy_count": 0,
            "sector_count": 0,
            "avg_buy_score": 0.0,
            "_buy_sum": 0.0,
            "_n": 0,
        }
    )
    for s in sectors:
        c = s.get("cycle") or "mixed"
        g = groups[c]
        g["cycle"] = c
        g["stock_count"] += s["stock_count"]
        g["hot_count"] += s["hot_count"]
        g["early_buy_count"] += s["early_buy_count"]
        g["sector_count"] += 1
        g["_buy_sum"] += s["avg_buy_score"] * s["stock_count"]
        g["_n"] += s["stock_count"]

    order = ["growth", "cyclical", "defensive", "thematic", "mixed"]
    out = []
    for cycle in order:
        if cycle not in groups:
            continue
        g = groups[cycle]
        n = g["_n"] or 1
        out.append(
            {
                "cycle": cycle,
                "label": {
                    "growth": "Growth",
                    "cyclical": "Cyclical",
                    "defensive": "Defensive",
                    "thematic": "Thematic",
                    "mixed": "Mixed",
                }.get(cycle, cycle),
                "stock_count": g["stock_count"],
                "hot_count": g["hot_count"],
                "early_buy_count": g["early_buy_count"],
                "sector_count": g["sector_count"],
                "avg_buy_score": round(g["_buy_sum"] / n, 1),
            }
        )
    return out