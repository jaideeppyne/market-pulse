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
    """Steeper reward for the freshest whale activity so today's moves rank first."""
    dt = _parse_dt(event.get("published_at") or event.get("created_at"))
    if not dt:
        return 0.0
    age_hours = max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0)
    if age_hours <= 1:
        return 30.0
    if age_hours <= 3:
        return 24.0
    if age_hours <= 6:
        return 18.0
    if age_hours <= 24:
        return 12.0
    if age_hours <= 72:
        return 6.0
    if age_hours <= 168:  # within a week, small residual
        return 2.0
    return 0.0


# Conviction multiplier by event type: legend/CEO/insider open-market buys are
# the highest-signal whale activity and should rank above generic filings.
_CONVICTION_WEIGHT = {
    "ceo_buy": 1.30,
    "ceo_buy_news": 1.25,
    "cfo_buy": 1.20,
    "director_buy": 1.15,
    "insider_open_market_buy": 1.15,
    "promoter_or_insider_buy": 1.12,
    "news_insider_buy": 1.05,
    "bulk_block_deal": 1.05,
    "sec_form4_filing": 1.00,
}


def _conviction_multiplier(event_type: str) -> float:
    return _CONVICTION_WEIGHT.get(event_type, 1.0)


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
        recency_pts = _recency_boost(strongest)
        conviction = _conviction_multiplier(event_type)
        # Freshness + conviction dominate; base/severity/scan provide the floor.
        candidate_score = (
            base * conviction
            + severity * 2.0
            + recency_pts * 1.5
            + min(scan_score, 100.0) * 0.2
        )

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
                "recency_boost": round(recency_pts, 1),
                "conviction": round(conviction, 2),
                "events": ordered[:5],
            }
        )

    candidates.sort(key=lambda c: c.get("candidate_score", 0), reverse=True)
    return candidates[:limit]
