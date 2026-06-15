from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


EVENT_BASE_SCORE = {
    "ceo_buy": 100.0,
    "ceo_buy_news": 92.0,
    "cfo_buy": 88.0,
    "director_buy": 82.0,
    "insider_open_market_buy": 78.0,
    "news_insider_buy": 72.0,
    "promoter_or_insider_buy": 76.0,
    "bulk_block_deal": 68.0,
    "sec_form4_filing": 58.0,
}


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _recency_boost(event: dict[str, Any]) -> float:
    dt = _parse_dt(event.get("published_at") or event.get("created_at"))
    if not dt:
        return 0.0
    age_hours = max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0)
    if age_hours <= 6:
        return 18.0
    if age_hours <= 24:
        return 12.0
    if age_hours <= 72:
        return 6.0
    return 0.0


def build_event_candidates(
    events_by_symbol: dict[str, list[dict[str, Any]]],
    symbols_cache: dict[str, dict[str, Any]] | None = None,
    *,
    limit: int = 120,
) -> list[dict[str, Any]]:
    """Rank symbols that have structured market events for lightweight triage."""
    symbols_cache = symbols_cache or {}
    candidates: list[dict[str, Any]] = []

    for symbol, events in events_by_symbol.items():
        if not symbol or not events:
            continue
        ordered = sorted(
            events,
            key=lambda e: (
                float(e.get("severity") or 0),
                _parse_dt(e.get("published_at") or e.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
        strongest = ordered[0]
        scan = symbols_cache.get(symbol) or {}
        metrics = scan.get("metrics") or {}
        event_type = strongest.get("event_type") or "market_event"
        base = EVENT_BASE_SCORE.get(event_type, 55.0)
        severity = float(strongest.get("severity") or 0)
        scan_score = float(metrics.get("buy_score") or scan.get("score") or 0)
        candidate_score = base + severity * 2.0 + _recency_boost(strongest) + min(scan_score, 100.0) * 0.2

        candidates.append(
            {
                "symbol": symbol,
                "market": strongest.get("market") or scan.get("market") or ("india" if symbol.endswith((".NS", ".BO")) else "uk" if symbol.endswith(".L") else "us"),
                "candidate_score": round(candidate_score, 1),
                "event_type": event_type,
                "event_count": len(ordered),
                "reason": strongest.get("title") or event_type,
                "source": strongest.get("source"),
                "published_at": strongest.get("published_at") or strongest.get("created_at"),
                "link": strongest.get("link"),
                "amount": strongest.get("amount"),
                "score": scan.get("score"),
                "buy_score": metrics.get("buy_score"),
                "price": metrics.get("price"),
                "day_chg_pct": metrics.get("day_chg_pct"),
                "rvol": metrics.get("rvol"),
                "has_scan": bool(scan),
                "events": ordered[:5],
            }
        )

    candidates.sort(key=lambda c: c.get("candidate_score", 0), reverse=True)
    return candidates[:limit]
