from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.engine.context import ScanContext
from app.engine.factor_registry import evaluate_factors
from app.engine.indicators import cup_handle_score, ma_support_resistance, rsi


@dataclass
class SignalResult:
    symbol: str
    market: str
    score: float = 0.0
    signals: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)
    factors_hit: int = 0
    factors_total: int = 76
    factor_details: list[dict] = field(default_factory=list)
    factor_breakdown: list[dict] = field(default_factory=list)


def analyze_symbol(
    symbol: str,
    market: str,
    hist: pd.DataFrame,
    info: dict[str, Any],
    news_count_24h: int,
    weights: dict[str, int] | None = None,  # legacy config, optional boost later
    earnings: dict[str, Any] | None = None,
    news_titles: list[str] | None = None,
    market_events: list[dict[str, Any]] | None = None,
    calendar: dict[str, Any] | None = None,
) -> SignalResult:
    res = SignalResult(symbol=symbol, market=market)
    if hist is None or hist.empty or len(hist) < 5:
        return res

    ctx = ScanContext(
        symbol=symbol,
        market=market,
        hist=hist,
        info=info or {},
        earnings=earnings,
        news_count=news_count_24h,
        news_titles=news_titles or [],
        market_events=market_events or [],
        calendar=calendar,
    )

    score, hits, alerts, metrics = evaluate_factors(ctx)
    ch, ch_meta = cup_handle_score(hist)
    metrics["cup_handle"] = ch
    metrics["cup_meta"] = ch_meta
    r = rsi(hist["Close"])
    metrics["rsi"] = round(r, 1) if r else metrics.get("rsi")

    # Simple DMA/EMA support/resistance levels + signal (user-friendly tech that works)
    try:
        tech = ma_support_resistance(hist["Close"])
        metrics["tech_levels"] = tech.get("levels", {})
        metrics["tech_signal"] = tech.get("signal")
        metrics["key_ma_support_res"] = tech  # for UI
    except Exception:
        pass

    res.score = score
    res.signals = metrics.get("signals", [])
    res.metrics = metrics
    res.alerts = list(dict.fromkeys(alerts))
    res.factors_hit = metrics.get("factors_hit", 0)
    res.factors_total = metrics.get("factors_total", 76)
    res.factor_details = metrics.get("factor_details", [])
    res.factor_breakdown = metrics.get("factor_breakdown", [])

    # === RICH REASONS for UI: multiple technical + fundamental + catalyst (solid why it's good) ===
    # Collect from positive factor hits + alerts + news signals. This is what gets published to frontend.
    reasons: list[dict] = []
    seen = set()
    for fd in (res.factor_details or []):
        if fd.get("pts", 0) > 0 or fd.get("cat") in ("fundamental", "valuation", "health", "ownership", "income", "catalyst"):
            key = fd.get("label", "")
            if key and key not in seen:
                reasons.append({
                    "text": key,
                    "category": fd.get("cat", "other"),
                    "fulfilled": True,
                    "evidence": fd.get("label"),
                    "pts": fd.get("pts", 0)
                })
                seen.add(key)
    for al in (res.alerts or []):
        if al and al not in seen:
            cat = "catalyst" if any(x in al.upper() for x in ["ORDER", "FII", "DIV", "PROMOTER", "EARNINGS"]) else "fundamental"
            reasons.append({"text": al, "category": cat, "fulfilled": True, "evidence": "news/event signal"})
            seen.add(al)
    # Add a few from news_titles for deep research feel (orders etc already boosted in registry)
    for nt in (news_titles or [])[:5]:
        nt_u = nt.upper()
        if any(k in nt_u for k in ["ORDER", "FII", "PROMOTER", "DIVIDEND", "CONTRACT"]) and nt not in seen:
            reasons.append({"text": f"News: {nt[:80]}", "category": "catalyst", "fulfilled": True, "evidence": nt})
            seen.add(nt)
    metrics["reasons"] = reasons[:12]  # cap for UI cleanliness, multiple not one
    metrics["fundamental_reasons_count"] = sum(1 for r in reasons if r["category"] in ("fundamental", "valuation", "health", "ownership", "income"))
    metrics["catalyst_reasons_count"] = sum(1 for r in reasons if r["category"] == "catalyst")
    res.metrics = metrics
    return res
