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

    # === RICH REASONS + EXPLICIT CRITERIA FULFILLMENT TRACKING ===
    # Multiple reasons (fund + tech + catalyst). Explicit list with fulfilled flags for UI highlighting.
    # This is published so frontend can show "which criteria got fulfilled".
    reasons: list[dict] = []
    criteria: list[dict] = []
    seen = set()
    for fd in (res.factor_details or []):
        if fd.get("pts", 0) > 0 or fd.get("cat") in ("fundamental", "valuation", "health", "ownership", "income", "catalyst"):
            key = fd.get("label", "")
            if key and key not in seen:
                item = {
                    "text": key,
                    "category": fd.get("cat", "other"),
                    "fulfilled": True,
                    "evidence": fd.get("label"),
                    "pts": fd.get("pts", 0)
                }
                reasons.append(item)
                criteria.append(item)
                seen.add(key)
    for al in (res.alerts or []):
        if al and al not in seen:
            cat = "catalyst" if any(x in al.upper() for x in ["ORDER", "FII", "DIV", "PROMOTER", "EARNINGS"]) else "fundamental"
            item = {"text": al, "category": cat, "fulfilled": True, "evidence": "news/event signal"}
            reasons.append(item)
            criteria.append(item)
            seen.add(al)
    # News mining for additional fulfilled criteria (deep research signal)
    for nt in (news_titles or [])[:5]:
        nt_u = nt.upper()
        if any(k in nt_u for k in ["ORDER", "FII", "PROMOTER", "DIVIDEND", "CONTRACT"]) and nt not in seen:
            item = {"text": f"News catalyst: {nt[:70]}", "category": "catalyst", "fulfilled": True, "evidence": nt}
            reasons.append(item)
            criteria.append(item)
            seen.add(nt)
    metrics["reasons"] = reasons[:12]
    metrics["criteria"] = criteria[:15]  # explicit fulfillment tracking
    metrics["fundamental_reasons_count"] = sum(1 for r in criteria if r.get("category") in ("fundamental", "valuation", "health", "ownership", "income"))
    metrics["catalyst_reasons_count"] = sum(1 for r in criteria if r.get("category") == "catalyst")
    metrics["fulfilled_criteria_count"] = len([c for c in criteria if c.get("fulfilled")])
    res.metrics = metrics

    # Strengthen deep research path: run extra mining + publish thesis for single stock
    # (uses yf info + news from crawlers). Only rich for promising India or high score cases to manage data/load.
    try:
        do_deep = (market == "india") or (score >= 45)
        if do_deep:
            research = deep_research_thesis(symbol, info or {}, news_titles or [], market, hist)
            metrics["deep_research"] = research
            metrics["thesis"] = research.get("thesis_summary", "")
            # Merge key findings into reasons for visibility
            for f in research.get("key_findings", [])[:4]:
                if f.get("criterion") and f.get("status") == "fulfilled":
                    metrics.setdefault("reasons", []).append({
                        "text": f"{f['criterion']}: {f.get('detail', '')}",
                        "category": "fundamental" if "Promoter" in f.get("criterion", "") or "FCF" in f.get("criterion", "") or "Valuation" in f.get("criterion", "") else "catalyst",
                        "fulfilled": True,
                        "evidence": f.get("value", "")
                    })
    except Exception:
        pass

    res.metrics = metrics
    return res


def deep_research_thesis(
    symbol: str,
    info: dict[str, Any],
    news_titles: list[str],
    market: str,
    hist: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Strengthened deep research path for a single stock.
    Uses extra yfinance mining (info already rich + optional more) + crawler news_titles.
    Publishes a structured thesis with multiple reasons for frontend users.
    Focused on India fundamentals + catalysts. Keeps data use low (no extra network if possible).
    """
    thesis: dict[str, Any] = {
        "symbol": symbol,
        "market": market,
        "thesis_summary": "",
        "key_findings": [],
        "sources": ["yfinance_info", "news_crawlers"],
        "research_timestamp": None,
    }
    findings = []
    # Mine info for deep fund details
    ph = info.get("heldPercentInsiders") or info.get("promoter_holding_pct")
    if market == "india" and ph and ph >= 0.35:
        findings.append({
            "criterion": "Promoter Holding",
            "status": "fulfilled",
            "value": f"{ph*100:.0f}%",
            "detail": "Strong promoter alignment (skin in the game)"
        })
    inst = info.get("heldPercentInstitutions")
    if market == "india" and inst and inst >= 0.12:
        findings.append({
            "criterion": "FII/Institutional Backing",
            "status": "fulfilled",
            "value": f"{inst*100:.0f}%",
            "detail": "Significant institutional / FII interest"
        })
    fcf_y = None
    mcap = info.get("marketCap")
    fcf = info.get("freeCashflow")
    if fcf and mcap and mcap > 0:
        fcf_y = (fcf / mcap) * 100
        if fcf_y >= 3:
            findings.append({
                "criterion": "FCF Yield",
                "status": "fulfilled",
                "value": f"{fcf_y:.1f}%",
                "detail": "Healthy free cash flow generation"
            })
    # Revenue / profit quality
    if info.get("revenueGrowth") and info.get("earningsGrowth"):
        rg = info["revenueGrowth"] * 100
        eg = info["earningsGrowth"] * 100
        if rg > 10 and eg > 10:
            findings.append({
                "criterion": "Dual Growth",
                "status": "fulfilled",
                "value": f"Rev {rg:.0f}% / Earn {eg:.0f}%",
                "detail": "Strong top and bottom line growth"
            })
    # Dividend
    dy = info.get("dividendYield")
    if dy and dy >= 0.02:
        findings.append({
            "criterion": "Dividend Yield",
            "status": "fulfilled",
            "value": f"{dy*100:.1f}%",
            "detail": "Attractive and potentially sustainable dividend"
        })
    # Valuation cheapness
    pe = info.get("trailingPE")
    if pe and pe < 18:
        findings.append({
            "criterion": "Valuation",
            "status": "fulfilled",
            "value": f"PE {pe:.1f}",
            "detail": "Reasonably valued relative to growth"
        })
    # News deep mining (from crawlers)
    news_upper = " ".join(news_titles or []).upper()
    news_findings = []
    if "ORDER" in news_upper or "CONTRACT" in news_upper:
        news_findings.append("Recent large order / contract win detected in news")
    if "FII" in news_upper or "INSTITUTIONAL BUY" in news_upper:
        news_findings.append("FII / institutional buying activity reported")
    if "PROMOTER" in news_upper and ("BUY" in news_upper or "INCREASE" in news_upper):
        news_findings.append("Promoter buying or stake increase signal")
    if "DIVIDEND" in news_upper:
        news_findings.append("Dividend related announcement (hike or special)")
    if news_findings:
        findings.append({
            "criterion": "News Catalysts",
            "status": "fulfilled",
            "value": f"{len(news_findings)} signals",
            "detail": " ; ".join(news_findings)
        })
        thesis["sources"].append("news_crawlers_deep")
    # Build summary
    if findings:
        thesis["key_findings"] = findings
        fulfilled = [f["criterion"] for f in findings if f.get("status") == "fulfilled"]
        thesis["thesis_summary"] = f"Strong fundamentals: {', '.join(fulfilled[:5])}. Multiple technical + fundamental + catalyst reasons support quality."
    else:
        thesis["thesis_summary"] = "Standard analysis completed. Check criteria for details."
    return thesis
