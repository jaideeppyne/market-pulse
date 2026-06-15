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


# === Simple, proven technical signals that work (DMA/EMA + support/resistance) ===
# User priority: technical or fundamental doesn't matter if it helps users make better decisions simply.

def ema(close: pd.Series, period: int = 20) -> float | None:
    if len(close) < period + 1:
        return None
    val = close.ewm(span=period, adjust=False).mean().iloc[-1]
    return float(val) if pd.notna(val) else None


def dma(close: pd.Series, period: int = 50) -> float | None:
    """50/200 DMA (simple moving average) - classic support/resistance and trend signal."""
    if len(close) < period + 1:
        return None
    val = close.rolling(period).mean().iloc[-1]
    return float(val) if pd.notna(val) else None


def ma_support_resistance(close: pd.Series, price: float | None = None) -> dict:
    """Simple support/resistance from key MAs (50DMA, 200DMA, 20EMA).
    Returns distances and a basic signal string. 'Support' when price near MA from above + recent low.
    These are easy-to-understand buy/sell signals that have worked for decades.
    """
    if len(close) < 50:
        return {"signal": None, "levels": {}}
    p = price or float(close.iloc[-1])
    ma50 = dma(close, 50)
    ma200 = dma(close, 200)
    ema20 = ema(close, 20)
    levels = {}
    if ma50:
        levels["50DMA"] = round(ma50, 2)
        dist50 = (p - ma50) / ma50 if ma50 else 0
        levels["dist_50dma_pct"] = round(dist50 * 100, 1)
    if ma200:
        levels["200DMA"] = round(ma200, 2)
        dist200 = (p - ma200) / ma200 if ma200 else 0
        levels["dist_200dma_pct"] = round(dist200 * 100, 1)
    if ema20:
        levels["20EMA"] = round(ema20, 2)
    # Simple signals
    signal = "neutral"
    if ma50 and ma200:
        if p > ma50 and p > ma200 and (ma50 > ma200):
            signal = "bullish_trend_support"
        elif p < ma50 and p < ma200:
            signal = "bearish_below"
        elif abs((p - ma50)/ma50) < 0.025 or abs((p - ma200)/ma200) < 0.03:
            signal = "near_key_ma"  # potential support or resistance
    if ema20 and ma50 and p > ema20 > ma50:
        signal = "bullish_ema_alignment"
    return {
        "signal": signal,
        "levels": levels,
        "price": round(p, 2),
    }


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


# Nitpicking every small technical detail for full accuracy
def bollinger_bands(close: pd.Series, period: int = 20, std: float = 2.0) -> dict:
    if len(close) < period:
        return {"signal": None}
    sma = close.rolling(period).mean()
    rstd = close.rolling(period).std()
    upper = sma + (std * rstd)
    lower = sma - (std * rstd)
    c = close.iloc[-1]
    bb_width = (upper.iloc[-1] - lower.iloc[-1]) / sma.iloc[-1] if sma.iloc[-1] else 0
    signal = "neutral"
    if c > upper.iloc[-1]:
        signal = "above_upper"
    elif c < lower.iloc[-1]:
        signal = "below_lower"
    elif bb_width < 0.1:  # squeeze - low vol opportunity
        signal = "squeeze"
    return {"upper": round(upper.iloc[-1], 2), "lower": round(lower.iloc[-1], 2), "width_pct": round(bb_width*100, 1), "signal": signal}

def stochastic_oscillator(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> dict:
    if len(close) < k_period + d_period:
        return {"signal": None}
    low_min = low.rolling(k_period).min()
    high_max = high.rolling(k_period).max()
    k = 100 * (close - low_min) / (high_max - low_min)
    d = k.rolling(d_period).mean()
    k_val = k.iloc[-1]
    d_val = d.iloc[-1]
    signal = "neutral"
    if k_val > 80 and d_val > 80:
        signal = "overbought"
    elif k_val < 20 and d_val < 20:
        signal = "oversold"
    elif k_val > d_val and k.iloc[-2] <= d.iloc[-2]:
        signal = "bull_cross"
    return {"k": round(k_val, 1), "d": round(d_val, 1), "signal": signal}

def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> dict:
    if len(close) < period:
        return {"signal": None}
    tp = (high + low + close) / 3
    sma = tp.rolling(period).mean()
    mad = (tp - sma).abs().rolling(period).mean()
    cci_val = (tp - sma) / (0.015 * mad)
    val = cci_val.iloc[-1]
    signal = "neutral"
    if val > 100:
        signal = "overbought"
    elif val < -100:
        signal = "oversold"
    return {"cci": round(val, 1), "signal": signal}

def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> dict:
    if len(close) < period + 1:
        return {"signal": None}
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx_val = dx.rolling(period).mean().iloc[-1]
    signal = "neutral"
    if adx_val > 25:
        signal = "trending"
    return {"adx": round(adx_val, 1), "signal": signal}

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period:
        return None
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])

def obv(close: pd.Series, volume: pd.Series) -> dict:
    if len(close) < 2:
        return {"signal": None}
    obv_val = (np.sign(close.diff()) * volume).cumsum().iloc[-1]
    # simple signal: rising obv with price = accumulation
    recent_obv = (np.sign(close.diff().tail(5)) * volume.tail(5)).sum()
    signal = "neutral"
    if recent_obv > 0 and close.iloc[-1] > close.iloc[-5]:
        signal = "accumulation"
    return {"obv": round(obv_val, 0), "signal": signal}

def ma_slope(close: pd.Series, period: int = 20) -> float | None:
    if len(close) < period:
        return None
    ma = close.rolling(period).mean()
    if len(ma) < 2:
        return None
    return float((ma.iloc[-1] - ma.iloc[-2]) / ma.iloc[-2] * 100) if ma.iloc[-2] else None

def volatility(close: pd.Series, period: int = 20) -> float | None:
    if len(close) < period:
        return None
    returns = close.pct_change()
    return float(returns.rolling(period).std().iloc[-1] * np.sqrt(252) * 100)  # annualized % 

def rate_of_change(close: pd.Series, period: int = 10) -> float | None:
    if len(close) < period + 1:
        return None
    return float((close.iloc[-1] - close.iloc[-period-1]) / close.iloc[-period-1] * 100)


def near_ma_pullback(close: pd.Series, ma_days: int = 50, band: float = 0.03) -> bool:
    if len(close) < ma_days + 5:
        return False
    ma = float(close.rolling(ma_days).mean().iloc[-1])
    price = float(close.iloc[-1])
    if ma <= 0:
        return False
    return abs(price / ma - 1) <= band and price >= ma * 0.97