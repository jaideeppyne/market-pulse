"""
Per-factor weights for buy/quality scoring.
Higher weight = stronger influence on rank (not equal checklist counting).

Tiers (multiplier on base points):
  S+ — named legend / politician buy (smart_money_*)
  S — whale / politician / insider / M&A / FDA / earnings today
  A — policy, contracts, FII, guidance, golden cross, squeeze setup
  B — entry setups, upgrades, famous investor (if not S)
  C — fundamentals, valuation, routine technicals
  D — soft / contextual signals
  R — risk penalties (subtracted, own scale)
"""
from __future__ import annotations

from app.engine.factor_catalog import FACTOR_CATALOG, ENTRY_FACTOR_IDS

# Tier multipliers applied to each factor's base points
TIER_S_PLUS = 6.5
TIER_S = 5.0
TIER_A = 3.5
TIER_B = 2.5
TIER_C = 1.5
TIER_D = 1.0

TIER_S_PLUS_IDS = frozenset({
    "smart_money_india_legend",
    "smart_money_us_legend",
    "smart_money_politician",
    "smart_money_foreign_india",
    "event_ceo_buy",
})

TIER_S_IDS = frozenset({
    "news_politician",
    "news_famous_investor",
    "news_insider_buy",
    "news_merger_acquisition",
    "news_fda_approval",
    "earnings_today",
    "news_fii_flow",
    "golden_cross_zone",
    "news_guidance_raise",
    "news_bulk_deal",
    "short_squeeze_setup",
    "news_short_squeeze",
    "event_cfo_buy",
    "event_director_buy",
    "event_insider_buy",
    "event_promoter_buy",
})

TIER_A_IDS = frozenset({
    "news_policy_gov",
    "news_order_contract",
    "news_turnaround",
    "news_stake_increase",
    "news_earnings_positive",
    "news_buyback",
    "news_analyst_positive",
    "news_init_coverage",
    "news_ai_theme",
    "news_semiconductor",
    "earnings_3d",
    "rvol_surge",
    "cup_handle",
    "macd_bullish",
    "news_rate_cut",
    "news_bank_npa",
    "event_bulk_block_deal",
    "india_defense_policy",
    "below_analyst_target",
    "room_to_run",
    "pre_breakout_vol",
    "rsi_oversold_bounce",
})

TIER_B_IDS = frozenset({
    *ENTRY_FACTOR_IDS,
    "news_new_ceo",
    "news_expansion",
    "news_partnership",
    "news_patent",
    "news_export_order",

    "news_tariff_relief",
    "news_sector_tailwind",
    "news_lawsuit_win",
    "news_burst",
    "earnings_pre_catalyst",
    "earnings_7d",
    "accumulation_day",
    "pullback_50dma",
    "rsi_turning_up",
    "reclaim_20dma",
    "cup_forming",
    "price_below_target",
    "peg_attractive",
    "fcf_yield_high",
})

# Risk: penalty points (not multiplied by base — flat weighted penalty)
RISK_PENALTY_WEIGHTS: dict[str, float] = {
    "extended_run": 18.0,
    "chase_risk": 14.0,
    "parabolic_move": 12.0,
    "already_at_high": 16.0,
    "rsi_overbought": 10.0,
    "high_short": 4.0,
    "distribution_day": 8.0,
}

# Category fallbacks for any catalog id not explicitly tiered
CATEGORY_TIER: dict[str, float] = {
    "catalyst": TIER_B,
    "news": TIER_B,
    "entry": TIER_B,
    "calendar": TIER_A,
    "technical": TIER_C,
    "volume": TIER_B,
    "momentum": TIER_C,
    "fundamental": TIER_C,
    "valuation": TIER_C,
    "health": TIER_D,
    "ownership": TIER_C,
    "income": TIER_D,
    "sector": TIER_B,
    "risk": 0.0,
}

_ID_TO_CATEGORY = {f.id: f.category for f in FACTOR_CATALOG}

# Scoring calibration (tuned so strong catalyst names can reach 85–100)
BUY_SCORE_SCALE = 0.42
QUALITY_SCORE_SCALE = 0.38
ENTRY_BUY_BOOST = 1.35
CATALYST_BUY_BOOST = 1.25
SMART_MONEY_BUY_BOOST = 1.55


def factor_weight(factor_id: str) -> float:
    if factor_id in TIER_S_PLUS_IDS:
        return TIER_S_PLUS
    if factor_id in TIER_S_IDS:
        return TIER_S
    if factor_id in TIER_A_IDS:
        return TIER_A
    if factor_id in TIER_B_IDS:
        return TIER_B
    cat = _ID_TO_CATEGORY.get(factor_id, "")
    if cat == "risk":
        return 0.0
    return CATEGORY_TIER.get(cat, TIER_D)


def weighted_points(factor_id: str, base_points: float) -> float:
    if base_points <= 0:
        return 0.0
    return round(base_points * factor_weight(factor_id), 2)


def risk_penalty(factor_id: str) -> float:
    return RISK_PENALTY_WEIGHTS.get(factor_id, 6.0)


def tier_label(factor_id: str) -> str:
    if factor_id in TIER_S_PLUS_IDS:
        return "S+"
    if factor_id in TIER_S_IDS:
        return "S"
    if factor_id in TIER_A_IDS:
        return "A"
    if factor_id in TIER_B_IDS:
        return "B"
    w = factor_weight(factor_id)
    if w >= TIER_C:
        return "C"
    return "D"


def weights_for_api() -> dict:
    return {
        "tiers": {
            "S+": {"multiplier": TIER_S_PLUS, "description": "Named legend / politician buy"},
            "S": {"multiplier": TIER_S, "description": "Strongest buy signals"},
            "A": {"multiplier": TIER_A, "description": "Major catalysts"},
            "B": {"multiplier": TIER_B, "description": "Entry + solid news"},
            "C": {"multiplier": TIER_C, "description": "Fundamentals / technicals"},
            "D": {"multiplier": TIER_D, "description": "Supporting signals"},
        },
        "tier_s_plus_factors": sorted(TIER_S_PLUS_IDS),
        "tier_s_factors": sorted(TIER_S_IDS),
        "risk_penalties": RISK_PENALTY_WEIGHTS,
    }
