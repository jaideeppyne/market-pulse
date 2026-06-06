from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 2:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    val = 100 - (100 / (1 + rs))
    v = val.iloc[-1]
    return float(v) if pd.notna(v) else None


def macd_signal(close: pd.Series) -> str | None:
    if len(close) < 35:
        return None
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
        return "bullish_cross"
    if macd.iloc[-1] > signal.iloc[-1]:
        return "bullish"
    if macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
        return "bearish_cross"
    return "bearish"


def cup_handle_score(hist: pd.DataFrame, lookback: int = 120) -> tuple[int, dict]:
    if len(hist) < lookback:
        return 0, {}
    seg = hist.tail(lookback)
    close = seg["Close"]
    high = float(seg["High"].max())
    low = float(close.min())
    left_high = float(close.iloc[:30].max())
    right_high = float(close.iloc[-30:max(31, len(close))].max())
    current = float(close.iloc[-1])
    rim_similar = abs(left_high - right_high) / high < 0.12 if high else False
    depth = (high - low) / high if high else 0
    good_depth = 0.12 < depth < 0.45
    near_high = current >= high * 0.88 if high else False
    handle = close.tail(20)
    handle_pb = (float(handle.max()) - float(handle.min())) / float(handle.max()) if len(handle) else 0
    handle_ok = 0.03 < handle_pb < 0.15
    score = sum([rim_similar, good_depth, near_high, handle_ok])
    return score, {
        "depth_pct": round(depth * 100, 1),
        "near_high_pct": round(current / high * 100, 1) if high else 0,
        "handle_pullback_pct": round(handle_pb * 100, 1),
    }


def ma_alignment(close: pd.Series) -> str | None:
    if len(close) < 200:
        if len(close) < 50:
            return None
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]
        c = close.iloc[-1]
        if c > ma20 > ma50:
            return "bull_stack"
        if c < ma20 < ma50:
            return "bear_stack"
        return "mixed"
    ma20 = close.rolling(20).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]
    ma200 = close.rolling(200).mean().iloc[-1]
    c = close.iloc[-1]
    if c > ma20 > ma50 > ma200:
        return "full_bull"
    if c > ma50:
        return "bull_partial"
    if c < ma20 < ma50:
        return "bear_stack"
    return "mixed"


def volume_trend(volume: pd.Series, window: int = 10) -> float | None:
    if len(volume) < window + 1:
        return None
    recent = volume.tail(window).mean()
    prior = volume.tail(window * 2).head(window).mean()
    if prior and prior > 0:
        return float(recent / prior)
    return None


def pct_52w_range(price: float, high: float | None, low: float | None) -> float | None:
    """0 = at 52w low, 1 = at 52w high."""
    if not high or not low or high <= low:
        return None
    return float((price - low) / (high - low))


def rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def rsi_turning_up(close: pd.Series) -> bool:
    if len(close) < 20:
        return False
    rs = rsi_series(close)
    r0, r1, r2 = rs.iloc[-1], rs.iloc[-2], rs.iloc[-5]
    if any(pd.isna(x) for x in (r0, r1, r2)):
        return False
    return float(r0) > float(r1) and float(r0) < 55 and float(r2) < 45


def higher_lows(close: pd.Series, lookback: int = 30) -> bool:
    if len(close) < lookback:
        return False
    seg = close.tail(lookback)
    lows_idx = []
    for i in range(2, len(seg) - 2):
        v = seg.iloc[i]
        if v < seg.iloc[i - 1] and v < seg.iloc[i - 2] and v <= seg.iloc[i + 1]:
            lows_idx.append((i, float(v)))
    if len(lows_idx) < 2:
        return False
    return lows_idx[-1][1] > lows_idx[-2][1]


def range_compression(close: pd.Series, days: int = 20) -> bool:
    if len(close) < days + 5:
        return False
    seg = close.tail(days)
    rng = (float(seg.max()) - float(seg.min())) / float(seg.mean())
    return rng < 0.08


def near_ma_pullback(close: pd.Series, ma_days: int = 50, band: float = 0.03) -> bool:
    if len(close) < ma_days + 5:
        return False
    ma = float(close.rolling(ma_days).mean().iloc[-1])
    price = float(close.iloc[-1])
    if ma <= 0:
        return False
    return abs(price / ma - 1) <= band and price >= ma * 0.97