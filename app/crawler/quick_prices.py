"""Fast price-only refresh for hot symbols (between full factor scans)."""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def _fetch_quick(symbols: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not symbols:
        return out
    try:
        data = yf.download(
            symbols,
            period="1mo",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=False,
            progress=False,
        )
    except Exception as e:
        logger.warning("Quick price fetch failed: %s", e)
        return out

    if data is None or data.empty:
        return out

    def patch_from_df(sym: str, df: pd.DataFrame) -> None:
        if df is None or df.empty or len(df) < 2:
            return
        close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
        price = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        day = (price / prev - 1) * 100 if prev else 0.0
        ret5 = (price / float(close.iloc[-6]) - 1) * 100 if len(close) > 6 else 0.0
        out[sym] = {
            "price": round(price, 4),
            "day_chg_pct": round(day, 2),
            "ret5d_pct": round(ret5, 2),
            "sparkline": [round(float(x), 4) for x in close.tail(30).tolist()],
        }

    if len(symbols) == 1:
        patch_from_df(symbols[0], data.dropna())
        return out

    for sym in symbols:
        try:
            if sym not in data.columns.get_level_values(0):
                continue
            patch_from_df(sym, data[sym].dropna())
        except Exception:
            continue
    return out


async def quick_refresh_symbols(symbols: list[str]) -> list[dict[str, Any]]:
    import asyncio

    patches = await asyncio.to_thread(_fetch_quick, symbols)
    return [{"symbol": s, **p} for s, p in patches.items()]