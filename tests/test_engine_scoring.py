"""Unit tests for app/engine/scoring._compute_scores.

Builds small synthetic FactorHit fixtures (no network / live data) to lock in
the buy_score vs quality_score behaviour, entry/catalyst/smart-money boosts,
the extension penalty, and monotonicity of quality_score.
"""
from __future__ import annotations

import pytest

from app.engine.scoring import _compute_scores
from app.engine.types import FactorHit


def hit(fid: str, category: str, points: float = 4.0, label: str = "x") -> FactorHit:
    return FactorHit(id=fid, category=category, label=label, points=points)


# --- empty / trivial ----------------------------------------------------------

def test_empty_hits_score_zero():
    buy, quality, ext, top, enriched = _compute_scores([], None)
    assert buy == 0.0
    assert quality == 0.0
    assert ext == 0.0
    assert top == []
    assert enriched == []


def test_only_zero_or_negative_point_hits_score_zero():
    hits = [hit("roe_strong", "fundamental", points=0.0)]
    buy, quality, ext, top, _ = _compute_scores(hits, None)
    assert buy == 0.0
    assert quality == 0.0


# --- enriched output carries tier metadata ------------------------------------

def test_enriched_hit_has_tier_and_weighted_points():
    hits = [hit("smart_money_us_legend", "catalyst", points=4.0)]
    _, _, _, _, enriched = _compute_scores(hits, None)
    e = enriched[0]
    assert e["tier"] == "S+"
    assert e["weight"] == 6.5
    assert e["weighted_points"] == pytest.approx(26.0)


# --- buy_score vs quality_score divergence ------------------------------------

def test_entry_bonus_lifts_buy_relative_to_quality():
    """An entry factor gets a 1.35x buy boost, so buy_score should be lifted
    relative to the same weighted points contributing only to quality."""
    entry_hits = [hit("room_to_run", "entry", points=5.0)]
    # a non-entry factor of the SAME weighted points (room_to_run is tier A = 3.5;
    # below_analyst_target is tier A entry... pick a plain A non-entry: news_policy_gov)
    plain_hits = [hit("news_policy_gov", "catalyst", points=5.0)]

    buy_entry, q_entry, _, _, _ = _compute_scores(entry_hits, None)
    buy_plain, q_plain, _, _, _ = _compute_scores(plain_hits, None)

    # quality of both is identical weighted points (same tier A multiplier)
    assert q_entry == q_plain
    # but the entry boost (1.35) beats the catalyst boost (1.25) on buy_score
    assert buy_entry > buy_plain


def test_extension_penalty_lowers_buy_but_not_quality():
    """A risk/extension factor must drag down buy_score while quality_score
    (which ignores risk weighting) stays put."""
    good = [hit("room_to_run", "entry", points=5.0)]
    good_plus_risk = good + [hit("extended_run", "risk", points=0.0)]

    buy_good, q_good, ext_good, _, _ = _compute_scores(good, None)
    buy_risk, q_risk, ext_risk, _, _ = _compute_scores(good_plus_risk, None)

    assert ext_good == 0.0
    assert ext_risk == pytest.approx(18.0)  # extended_run penalty
    assert buy_risk < buy_good
    assert q_risk == q_good  # quality unaffected by the risk factor


def test_pct_range_near_high_adds_extension_penalty():
    hits = [hit("room_to_run", "entry", points=5.0)]
    _, _, ext_mid, _, _ = _compute_scores(hits, 0.5)
    _, _, ext_92, _, _ = _compute_scores(hits, 0.93)
    _, _, ext_95, _, _ = _compute_scores(hits, 0.97)
    assert ext_mid == 0.0
    assert ext_92 == pytest.approx(6.0)
    assert ext_95 == pytest.approx(12.0)


# --- smart-money and catalyst feed buy_score ----------------------------------

def test_smart_money_boost_feeds_buy_score_more_than_plain_fundamental():
    sm = [hit("smart_money_us_legend", "catalyst", points=4.0)]
    fund = [hit("roe_strong", "fundamental", points=4.0)]
    buy_sm, _, _, _, _ = _compute_scores(sm, None)
    buy_fund, _, _, _, _ = _compute_scores(fund, None)
    # S+ tier (6.5) AND a 1.55 smart-money buy boost dwarfs a C fundamental
    assert buy_sm > buy_fund


def test_smart_money_outweighs_catalyst_for_same_points():
    """The smart-money buy boost (1.55) should beat a plain news catalyst
    boost (1.25) once we control for the tier multiplier by using the same
    weighted points contribution."""
    # smart_money_us_legend: tier S+ 6.5; news_merger_acquisition: tier S 5.0.
    # Use base points so weighted points are comparable-ish; assert the smart
    # money buy_score is strictly higher with equal base points (it has both a
    # higher tier and a higher buy boost).
    sm = [hit("smart_money_us_legend", "catalyst", points=4.0)]
    cat = [hit("news_merger_acquisition", "catalyst", points=4.0)]
    buy_sm, _, _, _, _ = _compute_scores(sm, None)
    buy_cat, _, _, _, _ = _compute_scores(cat, None)
    assert buy_sm > buy_cat


# --- monotonicity: adding a positive factor never lowers quality --------------

@pytest.mark.parametrize(
    "added",
    [
        ("roe_strong", "fundamental"),
        ("news_policy_gov", "catalyst"),
        ("room_to_run", "entry"),
        ("smart_money_us_legend", "catalyst"),
    ],
)
def test_adding_positive_factor_never_lowers_quality(added):
    base = [hit("dividend_yield", "income", points=3.0)]
    fid, cat = added
    bigger = base + [hit(fid, cat, points=4.0)]
    _, q_base, _, _, _ = _compute_scores(base, None)
    _, q_bigger, _, _, _ = _compute_scores(bigger, None)
    assert q_bigger >= q_base


def test_more_positive_factors_raise_quality_until_capped():
    one = [hit("news_policy_gov", "catalyst", points=4.0)]
    three = one + [
        hit("news_partnership", "catalyst", points=4.0),
        hit("roe_strong", "fundamental", points=4.0),
    ]
    _, q1, _, _, _ = _compute_scores(one, None)
    _, q3, _, _, _ = _compute_scores(three, None)
    assert q3 > q1


# --- scores are clamped to [0, 100] -------------------------------------------

def test_scores_clamped_to_100():
    big = [hit(f"smart_money_us_legend", "catalyst", points=50.0)] * 1  # huge points
    big = [hit("smart_money_us_legend", "catalyst", points=80.0)]
    buy, quality, _, _, _ = _compute_scores(big, None)
    assert 0.0 <= buy <= 100.0
    assert 0.0 <= quality <= 100.0


def test_buy_score_floored_at_zero_under_heavy_penalty():
    # only risk factors + near-high pct -> buy_raw can go negative, must clamp to 0
    hits = [
        hit("extended_run", "risk", points=0.0),
        hit("already_at_high", "risk", points=0.0),
    ]
    buy, quality, ext, _, _ = _compute_scores(hits, 0.99)
    assert buy == 0.0
    assert quality == 0.0
    assert ext > 0.0
