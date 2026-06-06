from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd
import yfinance as yf

from app.engine.signals import analyze_symbol
from app.db import insert_snapshot

logger = logging.getLogger(__name__)


def _fetch_info_calendar(sym: str) -> tuple[dict, dict | None]:
    info: dict = {}
    calendar = None
    try:
        t = yf.Ticker(sym)
        info = t.info or {}
        try:
            cal = t.calendar
            if isinstance(cal, dict) and cal:
                calendar = cal
        except Exception:
            pass
    except Exception:
        pass
    return info, calendar


def _fetch_batch(symbols: list[str]) -> dict[str, tuple[pd.DataFrame, dict, dict | None]]:
    """Sync batch download — run in thread pool."""
    out: dict[str, tuple[pd.DataFrame, dict, dict | None]] = {}
    if not symbols:
        return out

    try:
        data = yf.download(
            symbols,
            period="6mo",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
    except Exception as e:
        logger.error("Batch download error: %s", e)
        return out

    if data is None or data.empty:
        return out

    if len(symbols) == 1:
        sym = symbols[0]
        df = data.dropna()
        if not df.empty:
            info, calendar = _fetch_info_calendar(sym)
            out[sym] = (df, info, calendar)
        return out

    for sym in symbols:
        try:
            if sym not in data.columns.get_level_values(0):
                continue
            df = data[sym].dropna()
            if df.empty:
                continue
            info, calendar = _fetch_info_calendar(sym)
            out[sym] = (df, info, calendar)
        except Exception:
            continue
    return out


async def scan_symbols(
    symbols: list[str],
    market: str,
    news_counts: dict[str, int],
    weights: dict[str, int],
    earnings_by_symbol: dict[str, dict] | None = None,
    news_titles_by_symbol: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    raw = await asyncio.to_thread(_fetch_batch, symbols)
    earnings_by_symbol = earnings_by_symbol or {}
    news_titles_by_symbol = news_titles_by_symbol or {}
    results: list[dict[str, Any]] = []
    for sym, (hist, info, calendar) in raw.items():
        earn = earnings_by_symbol.get(sym)
        sig = analyze_symbol(
            sym,
            market,
            hist,
            info,
            news_counts.get(sym, 0),
            weights,
            earnings=earn,
            news_titles=news_titles_by_symbol.get(sym, []),
            calendar=calendar,
        )
        payload = {
            "symbol": sym,
            "market": market,
            "score": sig.score,
            "signals": sig.signals,
            "alerts": sig.alerts,
            "metrics": sig.metrics,
            "factors_hit": sig.factors_hit,
            "factors_total": sig.factors_total,
            "factor_details": sig.factor_details,
            "factor_breakdown": sig.factor_breakdown,
            "sparkline": [round(float(x), 4) for x in hist["Close"].tail(30).tolist()],
        }
        results.append(payload)
        if sig.score >= 40:
            await insert_snapshot(sym, market, payload, sig.score)
    return results