from __future__ import annotations

import math
from typing import Any

import numpy as np


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-50.0, min(50.0, x))))


def _count(row: dict[str, Any], category: str, status: str = "pass") -> int:
    return sum(
        1
        for f in (row.get("factor_breakdown") or [])
        if f.get("category") == category and f.get("status") == status
    )


def _risk_count(row: dict[str, Any]) -> int:
    return sum(1 for f in (row.get("factor_breakdown") or []) if f.get("status") == "risk")


def _feature_vector(row: dict[str, Any]) -> list[float]:
    m = row.get("metrics") or {}
    return [
        float(m.get("buy_score") or row.get("score") or 0),
        float(m.get("quality_score") or 0),
        float(m.get("day_chg_pct") or 0),
        float(m.get("ret5d_pct") or 0),
        float(m.get("ret20d_pct") or 0),
        float(m.get("rvol") or 0),
        float(m.get("rsi") or 50),
        float(m.get("pct_52w_range") or 50),
        float(_count(row, "entry")),
        float(_count(row, "catalyst") + _count(row, "news")),
        float(_count(row, "fundamental")),
        float(_count(row, "valuation")),
        float(_risk_count(row)),
        1.0 if m.get("has_smart_money") else 0.0,
        1.0 if m.get("has_market_event") else 0.0,
        float(m.get("extension_penalty") or 0),
    ]


def _confidence(row: dict[str, Any]) -> float:
    m = row.get("metrics") or {}
    score = 100.0
    required = ["price", "day_chg_pct", "rvol", "rsi", "sector"]
    score -= 5.0 * sum(1 for k in required if m.get(k) in (None, "", 0) and k != "day_chg_pct")
    fundamental_keys = ["pe", "pb", "peg", "fcf", "inst_pct", "insider_pct"]
    missing_fund = sum(1 for k in fundamental_keys if m.get(k) is None)
    score -= min(24.0, missing_fund * 4.0)
    if not row.get("sparkline") or len(row.get("sparkline") or []) < 15:
        score -= 10.0
    if m.get("news_24h", 0) == 0 and not m.get("has_market_event") and not m.get("has_smart_money"):
        score -= 5.0
    return round(max(10.0, min(100.0, score)), 1)


def _archetype(row: dict[str, Any]) -> str:
    m = row.get("metrics") or {}
    if m.get("has_market_event"):
        events = m.get("market_events") or []
        et = events[0].get("event_type") if events else ""
        if "ceo" in et:
            return "CEO Buy Catalyst"
        if "insider" in et or "director" in et or "cfo" in et:
            return "Insider Accumulation"
        return "Event-Driven Setup"
    if m.get("has_smart_money"):
        return "Smart Money Catalyst"
    if _count(row, "entry") >= 3:
        return "Early Base / Pullback"
    if _count(row, "catalyst") + _count(row, "news") >= 2:
        return "News Catalyst"
    if _count(row, "fundamental") + _count(row, "valuation") >= 6:
        return "Quality Value"
    if (m.get("rvol") or 0) >= 2:
        return "Volume Breakout"
    return "Mixed Multi-Factor"


def _opportunity_probability(row: dict[str, Any], confidence: float) -> float:
    m = row.get("metrics") or {}
    buy = float(m.get("buy_score") or row.get("score") or 0)
    quality = float(m.get("quality_score") or 0)
    entry = _count(row, "entry")
    catalysts = _count(row, "catalyst") + _count(row, "news")
    risks = _risk_count(row)
    event_boost = 13 if m.get("has_market_event") else 0
    smart_boost = 10 if m.get("has_smart_money") else 0
    extension = float(m.get("extension_penalty") or 0)
    z = (
        -2.2
        + buy / 34.0
        + quality / 85.0
        + entry * 0.16
        + catalysts * 0.18
        + event_boost / 28.0
        + smart_boost / 30.0
        - risks * 0.22
        - extension / 24.0
        + (confidence - 70.0) / 130.0
    )
    return round(_sigmoid(z) * 100, 1)


def annotate_ml_intel(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach ML-style ranking metadata to scan rows.

    Uses deterministic probability/confidence for every row and IsolationForest
    when a batch has enough rows. This is intentionally explainable and robust
    when no trained historical model exists yet.
    """
    if not rows:
        return rows

    vectors = np.array([_feature_vector(r) for r in rows], dtype=float)
    outlier_scores: list[float | None] = [None] * len(rows)
    if len(rows) >= 12:
        try:
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler

            scaled = StandardScaler().fit_transform(vectors)
            model = IsolationForest(contamination=min(0.2, max(0.03, 8 / len(rows))), random_state=42)
            model.fit(scaled)
            raw_scores = model.decision_function(scaled)
            lo = float(raw_scores.min())
            hi = float(raw_scores.max())
            rng = hi - lo or 1.0
            # Lower raw score means more unusual; expose higher number as "unusual opportunity".
            outlier_scores = [round((1.0 - ((float(s) - lo) / rng)) * 100, 1) for s in raw_scores]
        except Exception:
            pass

    for idx, row in enumerate(rows):
        m = row.setdefault("metrics", {})
        conf = _confidence(row)
        prob = _opportunity_probability(row, conf)
        nitpick = round(
            prob * 0.45
            + conf * 0.20
            + float(m.get("buy_score") or row.get("score") or 0) * 0.25
            + min(100.0, (_count(row, "entry") + _count(row, "catalyst")) * 8.0) * 0.10,
            1,
        )
        ml = {
            "opportunity_probability": prob,
            "data_confidence": conf,
            "nitpick_score": nitpick,
            "setup_archetype": _archetype(row),
            "unusual_setup_score": outlier_scores[idx],
            "model": "heuristic+isolation_forest" if outlier_scores[idx] is not None else "heuristic",
        }
        m["ml"] = ml
        m["data_confidence"] = conf
        m["nitpick_score"] = nitpick
        m["setup_archetype"] = ml["setup_archetype"]
        if outlier_scores[idx] is not None:
            m["unusual_setup_score"] = outlier_scores[idx]
    return rows
