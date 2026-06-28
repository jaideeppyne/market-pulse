"""Unit tests for the tiered factor-weight system (app/engine/factor_weights.py).

These guard the 7-tier multiplier table and risk penalties so a weight/tier
edit can never silently corrupt rankings without a test catching it.
"""
from __future__ import annotations

import pytest

from app.engine import factor_weights as fw
from app.engine.factor_catalog import FACTOR_CATALOG


_CATALOG_IDS = {f.id for f in FACTOR_CATALOG}


# --- tier multipliers are ordered and applied correctly -----------------------

def test_tier_multipliers_are_strictly_descending():
    """S+ must outrank S must outrank A ... down to D. If this breaks, the
    whole 'weighted, not checklist' premise is broken."""
    assert (
        fw.TIER_S_PLUS
        > fw.TIER_S
        > fw.TIER_A
        > fw.TIER_B
        > fw.TIER_C
        > fw.TIER_D
    )
    assert fw.TIER_S_PLUS == 6.5
    assert fw.TIER_D == 1.0


def test_factor_weight_resolves_each_tier():
    # S+ named smart money
    assert fw.factor_weight("smart_money_us_legend") == fw.TIER_S_PLUS
    # S strong signal
    assert fw.factor_weight("news_insider_buy") == fw.TIER_S
    # A major catalyst
    assert fw.factor_weight("news_policy_gov") == fw.TIER_A
    # B entry / solid news
    assert fw.factor_weight("news_partnership") == fw.TIER_B
    # C fundamental falls back via CATEGORY_TIER
    assert fw.factor_weight("roe_strong") == fw.TIER_C
    # D soft / income falls back to TIER_D
    assert fw.factor_weight("dividend_yield") == fw.TIER_D


def test_unknown_id_falls_back_to_tier_d():
    assert fw.factor_weight("totally_made_up_factor_id") == fw.TIER_D


def test_risk_category_factor_weight_is_zero():
    # risk factors should never add positive weighted points
    assert fw.factor_weight("extended_run") == 0.0
    assert fw.factor_weight("rsi_overbought") == 0.0


# --- the headline assertion: S+ smart money >> equal-points C fundamental -----

def test_s_plus_smart_money_dominates_c_fundamental_for_equal_base_points():
    base = 4.0
    s_plus = fw.weighted_points("smart_money_us_legend", base)  # 4 * 6.5 = 26
    c_fund = fw.weighted_points("roe_strong", base)             # 4 * 1.5 = 6
    assert s_plus == pytest.approx(26.0)
    assert c_fund == pytest.approx(6.0)
    # S+ should be far above (>= 4x) a C-tier factor with identical base points
    assert s_plus >= 4 * c_fund


# --- weighted_points behaviour ------------------------------------------------

def test_weighted_points_multiplies_base_by_weight():
    assert fw.weighted_points("news_insider_buy", 3.0) == pytest.approx(15.0)  # 3 * 5.0


def test_weighted_points_non_positive_base_returns_zero():
    assert fw.weighted_points("smart_money_us_legend", 0.0) == 0.0
    assert fw.weighted_points("smart_money_us_legend", -5.0) == 0.0


def test_weighted_points_is_rounded_to_two_dp():
    # 3.333 * 1.5 = 4.9995 -> rounds to 5.0
    assert fw.weighted_points("roe_strong", 3.333) == pytest.approx(5.0)


# --- risk penalties subtract (positive penalty values) ------------------------

def test_risk_penalty_returns_configured_value():
    assert fw.risk_penalty("extended_run") == 18.0
    assert fw.risk_penalty("already_at_high") == 16.0


def test_risk_penalty_unknown_id_uses_default():
    assert fw.risk_penalty("unconfigured_risk") == 6.0


def test_all_risk_penalties_are_positive():
    # penalties are subtracted in scoring, so each must be a positive magnitude
    for fid, pen in fw.RISK_PENALTY_WEIGHTS.items():
        assert pen > 0, f"{fid} risk penalty must be positive, got {pen}"


# --- tier_label behaviour -----------------------------------------------------

@pytest.mark.parametrize(
    "factor_id,expected",
    [
        ("smart_money_us_legend", "S+"),
        ("event_ceo_buy", "S+"),
        ("news_insider_buy", "S"),
        ("golden_cross_zone", "S"),
        ("news_policy_gov", "A"),
        ("news_partnership", "B"),
        ("roe_strong", "C"),
        ("dividend_yield", "D"),
    ],
)
def test_tier_label(factor_id, expected):
    assert fw.tier_label(factor_id) == expected


# --- dead-id guards: every tiered id must exist in the catalog ----------------

@pytest.mark.parametrize(
    "id_set_name",
    ["TIER_S_PLUS_IDS", "TIER_S_IDS", "TIER_A_IDS", "TIER_B_IDS"],
)
def test_tiered_ids_exist_in_catalog(id_set_name):
    """Guard against typos / dead ids: every id we explicitly tier must be a
    real factor in the catalog, otherwise the tier silently does nothing."""
    ids = getattr(fw, id_set_name)
    missing = sorted(i for i in ids if i not in _CATALOG_IDS)
    assert not missing, f"{id_set_name} references unknown factor ids: {missing}"


def test_risk_penalty_ids_exist_in_catalog():
    missing = sorted(i for i in fw.RISK_PENALTY_WEIGHTS if i not in _CATALOG_IDS)
    assert not missing, f"RISK_PENALTY_WEIGHTS references unknown ids: {missing}"


def _tier_overlaps() -> list[str]:
    sets = {
        "S+": fw.TIER_S_PLUS_IDS,
        "S": fw.TIER_S_IDS,
        "A": fw.TIER_A_IDS,
        "B": fw.TIER_B_IDS,
    }
    seen: dict[str, str] = {}
    dupes: list[str] = []
    for tier, ids in sets.items():
        for i in ids:
            if i in seen:
                dupes.append(f"{i} in both {seen[i]} and {tier}")
            seen[i] = tier
    return dupes


@pytest.mark.xfail(
    reason="KNOWN ENGINE BUG: TIER_B_IDS splats ENTRY_FACTOR_IDS, so several "
    "entry factors (room_to_run, pre_breakout_vol, below_analyst_target, "
    "short_squeeze_setup) also appear in TIER_A/TIER_S. factor_weight() resolves "
    "S+->S->A->B in order so the higher tier currently wins, but the overlap is "
    "fragile and confusing. App owner should de-duplicate the tier sets.",
    strict=True,
)
def test_no_id_appears_in_two_tiers():
    """An id in two tier sets makes tier resolution order-dependent and fragile."""
    dupes = _tier_overlaps()
    assert not dupes, f"factor ids appear in multiple tiers: {dupes}"


def test_tier_overlap_does_not_currently_corrupt_weights():
    """Even though some ids are double-listed (see xfail above), the *effective*
    weight must still be the higher (earlier-checked) tier, never the B fallback.
    This pins the current behaviour so a future refactor stays consistent."""
    # these are listed in both an A/S tier AND (via ENTRY splat) tier B
    assert fw.factor_weight("room_to_run") == fw.TIER_A
    assert fw.factor_weight("pre_breakout_vol") == fw.TIER_A
    assert fw.factor_weight("below_analyst_target") == fw.TIER_A
    assert fw.factor_weight("short_squeeze_setup") == fw.TIER_S


def test_weights_for_api_exposes_descending_multipliers():
    api = fw.weights_for_api()
    tiers = api["tiers"]
    assert tiers["S+"]["multiplier"] > tiers["S"]["multiplier"] > tiers["A"]["multiplier"]
    assert set(api["risk_penalties"]) == set(fw.RISK_PENALTY_WEIGHTS)
