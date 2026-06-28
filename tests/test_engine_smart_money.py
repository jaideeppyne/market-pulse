"""Unit tests for app/engine/smart_money_intel.analyze_smart_money.

Locks in named-investor detection, the buy-context requirement, and the
non-equity false-positive guard (e.g. "buys a flat") so the regex registry
can't drift into firing on irrelevant headlines.
"""
from __future__ import annotations

from app.engine.smart_money_intel import analyze_smart_money


# --- positive detection: legend + buy context ---------------------------------

def test_us_legend_buy_headline_matches():
    intel = analyze_smart_money(
        ["Warren Buffett buys a stake in OXY in open-market purchase"], market="us"
    )
    assert intel.us_legend is True
    assert any(m.entity_id == "warren_buffett" for m in intel.matches)
    assert intel.primary_alert is not None
    assert "Buffett" in intel.primary_alert


def test_india_legend_buy_headline_matches():
    intel = analyze_smart_money(
        ["Ashish Kacholia adds to his stake in a smallcap, latest shareholding shows"],
        market="india",
    )
    assert intel.india_legend is True
    assert any(m.entity_id == "ashish_kacholia" for m in intel.matches)


# --- buy-context required where configured ------------------------------------

def test_legend_name_without_buy_context_does_not_match():
    """A legend merely *mentioned* (no buy/stake/accumulate language) must NOT
    fire — require_buy defaults to True for the legends."""
    intel = analyze_smart_money(
        ["Warren Buffett shares his views on inflation at annual conference"],
        market="us",
    )
    assert intel.us_legend is False
    assert intel.matches == []


def test_require_buy_false_entity_matches_without_buy_word():
    """FII flow entries set require_buy=False, so a flow headline should fire
    even without an explicit buy verb."""
    intel = analyze_smart_money(
        ["FII inflow into Indian equities continues for a third session"],
        market="india",
    )
    assert intel.foreign_india is True
    assert any(m.entity_id == "fii_buy_india" for m in intel.matches)


# --- false-positive guard: non-equity purchase context ------------------------

def test_legend_buying_an_apartment_does_not_match():
    """The headline names a tracked legend with a buy verb, but the purchase is
    a flat/apartment — must be suppressed by NON_EQUITY_PURCHASE_CONTEXT."""
    intel = analyze_smart_money(
        ["Vijay Kedia buys a luxury apartment in Mumbai for record price"],
        market="india",
    )
    assert intel.india_legend is False
    assert intel.matches == []


def test_legend_buying_house_property_does_not_match():
    intel = analyze_smart_money(
        ["Warren Buffett bought a vacation home / villa in California"],
        market="us",
    )
    assert intel.us_legend is False
    assert intel.matches == []


def test_non_equity_word_does_not_block_genuine_equity_buy():
    """If the headline mentions property words BUT also has clear equity terms
    (stake/shares), the match should still go through (guard has an override)."""
    intel = analyze_smart_money(
        ["Vijay Kedia buys shares / increases stake even as he sells a flat"],
        market="india",
    )
    assert intel.india_legend is True


# --- market scoping -----------------------------------------------------------

def test_us_market_filters_out_india_legends():
    intel = analyze_smart_money(
        ["Ashish Kacholia buys a big stake in this smallcap"], market="us"
    )
    assert intel.india_legend is False


def test_no_titles_returns_empty_intel():
    intel = analyze_smart_money([], market="both")
    assert intel.matches == []
    assert intel.primary_alert is None


# --- dedup: same entity only matched once -------------------------------------

def test_same_entity_only_counted_once_across_titles():
    intel = analyze_smart_money(
        [
            "Warren Buffett buys more BAC, raises holding",
            "Berkshire bought additional shares disclosure filed",
        ],
        market="us",
    )
    buffett_hits = [m for m in intel.matches if m.entity_id == "warren_buffett"]
    assert len(buffett_hits) == 1


# --- regression: tightened false positives (bare surnames / loose BUY_CONTEXT) ---

def _ids(intel):
    return {m.entity_id for m in intel.matches}


def test_portfolio_mention_no_longer_fires():
    """Old loose BUY_CONTEXT fired on the word 'portfolio' alone — it must not."""
    intel = analyze_smart_money(
        ["Mutual fund reveals its top portfolio holdings for the quarter"], market="us"
    )
    assert intel.matches == []


def test_13f_filing_alone_no_longer_fires():
    """A 13F quarterly filing mention is not a fresh buy and must not fire."""
    intel = analyze_smart_money(
        ["Hedge fund 13F filing shows positions as of last quarter"], market="us"
    )
    assert intel.matches == []


def test_bare_entry_word_no_longer_fires():
    intel = analyze_smart_money(
        ["Company makes its entry into the European market"], market="us"
    )
    assert intel.matches == []


def test_stake_word_without_buy_verb_no_longer_fires():
    """'stake' alone (no acquisition verb) is too loose — must not fire."""
    intel = analyze_smart_money(
        ["Promoter stake in the company remains unchanged at 51%"], market="india"
    )
    assert intel.matches == []


def test_single_token_fund_needs_explicit_buy_verb():
    """BlackRock / SoftBank named without a buy/stake verb must NOT fire."""
    assert analyze_smart_money(
        ["BlackRock CEO Larry Fink comments on markets in interview"], market="us"
    ).matches == []
    assert analyze_smart_money(
        ["SoftBank reports a quarterly loss amid the tech slump"], market="us"
    ).matches == []


def test_single_token_fund_fires_with_buy_verb():
    intel = analyze_smart_money(["BlackRock acquires a 5% stake in the company"], market="us")
    assert "blackrock" in _ids(intel)
    intel2 = analyze_smart_money(["Coatue buys stake in an AI startup"], market="us")
    assert "coatue" in _ids(intel2)


def test_bare_surname_word_boundary_no_substring_false_positive():
    """'damani' must not match inside an unrelated word like 'Damaniya', and
    'icahn' must not match a substring."""
    assert analyze_smart_money(
        ["Mr Damaniya opens a new restaurant chain and buys equipment"], market="india"
    ).matches == []
    assert analyze_smart_money(
        ["The made-up word ichahn appears here, nothing to buy"], market="us"
    ).matches == []


def test_pelosi_mention_without_trade_no_longer_fires():
    intel = analyze_smart_money(
        ["Nancy Pelosi gives a speech on healthcare reform"], market="us"
    )
    assert intel.matches == []


def test_pelosi_real_purchase_still_fires():
    intel = analyze_smart_money(
        ["Nancy Pelosi purchased NVDA shares, disclosure shows"], market="us"
    )
    assert "nancy_pelosi" in _ids(intel)


def test_bare_surname_real_buy_still_fires():
    """Bare surname WITH a genuine acquisition verb must still fire."""
    assert "radhakishan_damani" in _ids(
        analyze_smart_money(["Radhakishan Damani buys stake in this FMCG firm"], market="india")
    )
    assert "carl_icahn" in _ids(
        analyze_smart_money(["Carl Icahn raises stake in the energy company"], market="us")
    )
    assert "michael_burry" in _ids(
        analyze_smart_money(["Michael Burry buys shares of a regional bank"], market="us")
    )


# --- enrichment: structured fields surfaced for the Radar / frontend ----------

def test_match_carries_enriched_fields():
    intel = analyze_smart_money(
        ["Ashish Kacholia adds to his stake in a smallcap"], market="india"
    )
    m = next(x for x in intel.matches if x.entity_id == "ashish_kacholia")
    assert m.investor_type == "legend"
    assert m.action == "stake_increase"
    assert m.recency.get("detected_at") and "age_seconds" in m.recency
    assert m.blurb  # reuses registry 'quality'


def test_to_metrics_exposes_enriched_keys_for_frontend():
    """The snapshot the Radar reads must include investor_type/action/recency/blurb
    both at the top level and on each hit (additive — existing keys preserved)."""
    intel = analyze_smart_money(
        ["Warren Buffett buys a stake in OXY in open-market purchase"], market="us"
    )
    metrics = intel.to_metrics()
    # existing keys still present
    for legacy in ("hits", "names", "primary_alert", "us_legend"):
        assert legacy in metrics
    # new top-level enriched keys
    for key in ("investor_type", "action", "recency", "blurb"):
        assert key in metrics
    assert metrics["investor_type"] == "legend"
    # each hit carries the enriched keys too
    hit = metrics["hits"][0]
    for key in ("investor_type", "action", "recency", "blurb"):
        assert key in hit


def test_fii_action_classified():
    intel = analyze_smart_money(
        ["FII inflow into Indian equities continues for a third session"], market="india"
    )
    m = next(x for x in intel.matches if x.entity_id == "fii_buy_india")
    assert m.investor_type == "fii"
