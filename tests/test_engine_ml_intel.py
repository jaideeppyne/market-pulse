"""Unit tests for app/engine/ml_intel confidence scoring.

Confirms that missing fundamentals / required fields reduce data_confidence
and that a complete row scores high. Uses small synthetic rows (no network).
"""
from __future__ import annotations

from app.engine.ml_intel import _confidence, annotate_ml_intel


def _complete_row() -> dict:
    return {
        "score": 80,
        "metrics": {
            "price": 100.0,
            "day_chg_pct": 1.2,
            "rvol": 2.1,
            "rsi": 55,
            "sector": "Technology",
            "pe": 22.0,
            "pb": 4.0,
            "peg": 1.3,
            "fcf": 1.0e9,
            "inst_pct": 60.0,
            "insider_pct": 12.0,
            "buy_score": 80.0,
            "quality_score": 70.0,
            "has_market_event": True,
            "news_24h": 3,
        },
        "sparkline": list(range(30)),
        "factor_breakdown": [],
    }


def test_complete_row_scores_high_confidence():
    conf = _confidence(_complete_row())
    assert conf >= 90.0


def test_missing_fundamentals_reduce_confidence():
    full = _complete_row()
    sparse = _complete_row()
    for k in ["pe", "pb", "peg", "fcf", "inst_pct", "insider_pct"]:
        sparse["metrics"][k] = None
    conf_full = _confidence(full)
    conf_sparse = _confidence(sparse)
    assert conf_sparse < conf_full
    # six missing fundamentals -> capped at -24
    assert conf_full - conf_sparse >= 24.0 - 0.01


def test_missing_required_fields_reduce_confidence():
    full = _complete_row()
    sparse = _complete_row()
    # drop required fields (price, rvol, rsi, sector) -> 5 pts each
    for k in ["price", "rvol", "rsi", "sector"]:
        sparse["metrics"][k] = None
    assert _confidence(sparse) < _confidence(full)


def test_short_sparkline_reduces_confidence():
    full = _complete_row()
    short = _complete_row()
    short["sparkline"] = list(range(5))  # < 15
    assert _confidence(short) == _confidence(full) - 10.0


def test_confidence_has_a_floor_of_10():
    barren = {
        "score": 0,
        "metrics": {},
        "sparkline": [],
        "factor_breakdown": [],
    }
    assert _confidence(barren) >= 10.0


def test_annotate_attaches_ml_block_with_confidence():
    rows = [_complete_row()]
    out = annotate_ml_intel(rows)
    m = out[0]["metrics"]
    assert "ml" in m
    assert m["ml"]["data_confidence"] == m["data_confidence"]
    assert 0.0 <= m["ml"]["opportunity_probability"] <= 100.0
    assert m["ml"]["setup_archetype"]


def test_annotate_handles_empty_rows():
    assert annotate_ml_intel([]) == []
