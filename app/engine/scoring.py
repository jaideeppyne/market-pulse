"""Weighted buy / quality score computation."""
from __future__ import annotations

from app.engine.factor_catalog import ENTRY_FACTOR_IDS, RISK_EXTENSION_IDS
from app.engine.types import FactorHit
from app.engine.factor_weights import (
    BUY_SCORE_SCALE,
    CATALYST_BUY_BOOST,
    ENTRY_BUY_BOOST,
    QUALITY_SCORE_SCALE,
    SMART_MONEY_BUY_BOOST,
    factor_weight,
    risk_penalty,
    tier_label,
    weighted_points,
)

CATALYST_PREFIX = "news_"
SMART_MONEY_PREFIX = "smart_money_"


def _compute_scores(
    hits: list[FactorHit],
    pct_rng: float | None,
) -> tuple[float, float, float, list[dict], list[dict]]:
    """
    Returns (buy_score, quality_score, extension_penalty, top_weighted_hits, enriched_hits).
    """
    positive = [x for x in hits if x.points > 0]

    enriched: list[dict] = []
    quality_w = 0.0
    entry_w = 0.0
    catalyst_w = 0.0

    for h in positive:
        w = factor_weight(h.id)
        wp = weighted_points(h.id, h.points)
        quality_w += wp
        if h.id in ENTRY_FACTOR_IDS:
            entry_w += wp
        if h.id.startswith(SMART_MONEY_PREFIX):
            catalyst_w += wp * SMART_MONEY_BUY_BOOST
        elif h.id.startswith(CATALYST_PREFIX) or h.category == "catalyst":
            catalyst_w += wp
        enriched.append(
            {
                "id": h.id,
                "category": h.category,
                "label": h.label,
                "points": h.points,
                "weight": w,
                "tier": tier_label(h.id),
                "weighted_points": wp,
            }
        )

    ext_pen = 0.0
    for h in hits:
        if h.id in RISK_EXTENSION_IDS or h.id in {
            "high_short",
            "distribution_day",
            "rsi_overbought",
        }:
            ext_pen += risk_penalty(h.id)
    if pct_rng is not None and pct_rng >= 0.95:
        ext_pen += 12.0
    elif pct_rng is not None and pct_rng >= 0.92:
        ext_pen += 6.0

    quality_score = min(100.0, round(quality_w * QUALITY_SCORE_SCALE, 1))

    buy_raw = (
        entry_w * ENTRY_BUY_BOOST
        + catalyst_w * CATALYST_BUY_BOOST
        + (quality_w - entry_w - catalyst_w) * 0.85
        - ext_pen
    )
    buy_score = min(100.0, max(0.0, round(buy_raw * BUY_SCORE_SCALE, 1)))

    top_weighted = sorted(enriched, key=lambda x: x["weighted_points"], reverse=True)[:12]

    return buy_score, quality_score, ext_pen, top_weighted, enriched