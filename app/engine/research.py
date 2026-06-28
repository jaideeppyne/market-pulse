"""Per-stock 'research' synthesis for the UI.

Turns the factor breakdown + curated NSE/BSE quality tags into a graded,
multi-reason "why this stock is good" view, grouped by theme. Pure, offline,
free — no extra network. India-specific signals (promoter/FII/leadership/
dividend/balance-sheet) come from data/quality_seed.json since Yahoo's
fundamentals endpoint is rate-limited from a free datacenter IP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_SEED_PATH = Path(os.getenv("QUALITY_SEED_PATH", _ROOT / "data" / "quality_seed.json"))

_seed: dict[str, dict] = {}
_loaded = False


def _load() -> dict[str, dict]:
    global _loaded, _seed
    if _loaded:
        return _seed
    try:
        raw = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
        _seed = {k.upper(): v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)}
    except Exception:
        _seed = {}
    _loaded = True
    return _seed


# factor category -> friendly research group
_GROUP = {
    "fundamental": "Profits & Cash Flow",
    "valuation": "Valuation",
    "health": "Balance Sheet",
    "ownership": "Ownership & Backing",
    "income": "Dividends",
    "catalyst": "Catalysts",
    "news": "Catalysts",
    "sector": "Sector Edge",
    "technical": "Technicals",
    "momentum": "Technicals",
    "volume": "Technicals",
    "entry": "Entry Timing",
    "calendar": "Upcoming Events",
}
_GROUP_ORDER = [
    "Moat & Leadership", "Profits & Cash Flow", "Valuation", "Balance Sheet",
    "Ownership & Backing", "Dividends", "Catalysts", "Sector Edge",
    "Technicals", "Entry Timing", "Upcoming Events",
]


def _quality_reasons(sym: str) -> tuple[list[dict[str, str]], int, list[str]]:
    """Return (grouped quality reasons, quality points, headline tags) from the seed."""
    q = _load().get((sym or "").upper())
    if not q:
        return [], 0, []
    reasons: list[dict[str, str]] = []
    tags: list[str] = []
    pts = 0
    leader = q.get("leader")
    if leader:
        reasons.append({"group": "Moat & Leadership", "text": f"Market leader in {leader}"})
        tags.append("Market leader")
        pts += 22
    if q.get("compounder"):
        reasons.append({"group": "Moat & Leadership", "text": "Proven long-term compounder"})
        tags.append("Compounder")
        pts += 14
    if q.get("promoter"):
        reasons.append({"group": "Ownership & Backing", "text": "Strong promoter holding — skin in the game"})
        tags.append("Strong promoter")
        pts += 12
    if q.get("fii"):
        reasons.append({"group": "Ownership & Backing", "text": "Strong FII / institutional backing"})
        tags.append("FII backed")
        pts += 12
    if q.get("fcf"):
        reasons.append({"group": "Profits & Cash Flow", "text": "Consistently strong free-cash-flow generation"})
        tags.append("Strong FCF")
        pts += 10
    if q.get("low_debt"):
        reasons.append({"group": "Balance Sheet", "text": "Low-debt, strong balance sheet"})
        tags.append("Low debt")
        pts += 9
    if q.get("div"):
        reasons.append({"group": "Dividends", "text": "Consistent / healthy dividend payer"})
        tags.append("Dividends")
        pts += 8
    if q.get("orders"):
        reasons.append({"group": "Catalysts", "text": "Strong order book / large contract wins"})
        tags.append("Order book")
        pts += 8
    return reasons, pts, tags


def build_research(row: dict[str, Any]) -> dict[str, Any]:
    sym = row.get("symbol") or ""
    breakdown = row.get("factor_breakdown") or []
    m = row.get("metrics") or {}

    # 1) reasons from the live factor breakdown (passed checks)
    grouped: dict[str, list[dict[str, Any]]] = {}
    fund_pts = 0.0
    for f in breakdown:
        if f.get("status") != "pass":
            continue
        cat = f.get("category") or "technical"
        group = _GROUP.get(cat, "Technicals")
        text = f.get("label") or f.get("name") or f.get("id")
        if not text:
            continue
        grouped.setdefault(group, []).append({
            "text": text, "weight": float(f.get("weighted_points") or f.get("points") or 0),
        })
        if cat in ("fundamental", "valuation", "health", "ownership", "income"):
            fund_pts += float(f.get("points") or 0)

    # 2) curated quality reasons (India-specific)
    qreasons, qpts, tags = _quality_reasons(sym)
    for r in qreasons:
        grouped.setdefault(r["group"], []).insert(0, {"text": r["text"], "weight": 99})

    # 3) grade from fundamental factor strength + curated quality
    quality_score = min(100, round(fund_pts * 4.0 + qpts))
    if quality_score >= 80:
        grade = "A+"
    elif quality_score >= 66:
        grade = "A"
    elif quality_score >= 50:
        grade = "B"
    elif quality_score >= 34:
        grade = "C"
    else:
        grade = "D"
    seed = _load().get(sym.upper(), {})
    fundamentally_strong = quality_score >= 52 or bool(seed.get("leader") and (seed.get("promoter") or seed.get("fii")))

    # 4) ordered groups, de-duped, sorted by reason weight
    groups: list[dict[str, Any]] = []
    total_reasons = 0
    for name in _GROUP_ORDER:
        items = grouped.get(name)
        if not items:
            continue
        seen: set[str] = set()
        uniq = []
        for it in sorted(items, key=lambda x: x.get("weight", 0), reverse=True):
            t = it["text"]
            if t in seen:
                continue
            seen.add(t)
            uniq.append(t)
        groups.append({"title": name, "reasons": uniq[:6]})
        total_reasons += len(uniq[:6])

    # 5) one-line summary
    lead_bits = tags[:3] or [g["reasons"][0] for g in groups[:2] if g["reasons"]]
    summary = (
        f"Grade {grade} — {', '.join(lead_bits)}." if lead_bits
        else f"Grade {grade} — {total_reasons} supporting signals."
    )

    # 6) curated intelligence (business, what-to-watch, valuation, peers, archetype)
    profile = None
    archetype = None
    try:
        from app.engine.stock_profiles import profile_for
        _sector = m.get("sector") or row.get("sector")
        profile = profile_for(sym, _sector)
        if profile:
            archetype = profile.get("archetype")
    except Exception:
        profile = None

    return {
        "grade": grade,
        "quality_score": quality_score,
        "fundamentally_strong": fundamentally_strong,
        "tags": tags,
        "reason_count": total_reasons,
        "groups": groups,
        "summary": summary,
        "archetype": archetype,
        "profile": profile,
    }
