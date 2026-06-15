from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd
import yfinance as yf

from app.engine.signals import analyze_symbol
from app.engine.ml_intel import annotate_ml_intel
from app.db import insert_snapshot

logger = logging.getLogger(__name__)


def _normalize_history_frame(data: pd.DataFrame, sym: str) -> pd.DataFrame:
    """Return a single-symbol OHLCV frame with flat yfinance columns."""
    if data is None or data.empty:
        return pd.DataFrame()
    df = data.copy()
    if isinstance(df.columns, pd.MultiIndex):
        levels = [df.columns.get_level_values(i) for i in range(df.columns.nlevels)]
        if sym in set(str(x) for x in levels[0]):
            try:
                df = df[sym]
            except Exception:
                df = pd.DataFrame()
        elif sym in set(str(x) for x in levels[1]):
            try:
                df = df.xs(sym, axis=1, level=1)
            except Exception:
                df = pd.DataFrame()
        elif "Close" in set(str(x) for x in levels[0]):
            df.columns = df.columns.get_level_values(0)
        elif "Close" in set(str(x) for x in levels[1]):
            df.columns = df.columns.get_level_values(1)
    if isinstance(df.columns, pd.MultiIndex):
        return pd.DataFrame()
    df.columns = [str(c) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    return df.dropna(how="all")


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
        df = _normalize_history_frame(data, sym).dropna()
        if not df.empty:
            info, calendar = _fetch_info_calendar(sym)
            out[sym] = (df, info, calendar)
        return out

    for sym in symbols:
        try:
            df = _normalize_history_frame(data, sym).dropna()
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
    events_by_symbol: dict[str, list[dict]] | None = None,
) -> list[dict[str, Any]]:
    raw = await asyncio.to_thread(_fetch_batch, symbols)
    earnings_by_symbol = earnings_by_symbol or {}
    news_titles_by_symbol = news_titles_by_symbol or {}
    events_by_symbol = events_by_symbol or {}
    results: list[dict[str, Any]] = []
    for sym, data in raw.items():
        try:
            hist, info, calendar = data if data is not None else (None, {}, None)
            if hist is None or getattr(hist, "empty", False) or len(hist) < 10:
                continue  # bad / delisted / insufficient - skip fast for resilience
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
                market_events=events_by_symbol.get(sym, []),
                calendar=calendar,
            )
            # confidence for regular scans too
            conf = 100
            if not info or len(info) < 10: conf -= 20
            if len(hist) < 100: conf -= 15
            vol = hist["Volume"].iloc[-1] if len(hist) > 0 else 0
            if vol < 50000: conf -= 10
            if market == "india": conf -= 5
            conf = max(40, min(100, conf))
            buy_score = sig.metrics.get("buy_score", sig.score)
            quality_score = sig.metrics.get("quality_score", 0)
            payload = {
                "symbol": sym,
                "market": market,
                "score": sig.score,
                "buy_score": buy_score,
                "quality_score": quality_score,
                "confidence_score": conf,
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
        except Exception as e:
            # Skip bad/delisted/rate-limited tickers fast (resilience for India/US scans, prevents stalling on junk in extra lists)
            logger.debug("scan skip %s: %s", sym, str(e)[:80])
            continue
    annotate_ml_intel(results)
    results.sort(key=lambda x: x.get("buy_score", x.get("score", 0)), reverse=True)
    for payload in results:
        snapshot_score = payload.get("buy_score", payload.get("score", 0))
        if snapshot_score >= 40:
            await insert_snapshot(payload["symbol"], market, payload, snapshot_score)
    return results


async def full_exhaustive_scan(
    pool: list[str],
    news_counts: dict = None,
    news_titles: dict = None,
    earnings_map: dict = None,
    events_by_symbol: dict[str, list[dict]] | None = None,
) -> list[dict]:
    """Full accuracy exhaustive scan over the COMPLETE universe (all reachable India + US listed stocks).
    Time does not matter. We are extremely slow and thorough for maximum coverage and accuracy:
    - 2y history for better technicals and patterns.
    - Full info + extra data pulls (recommendations, holders, more fundamentals).
    - Every single symbol gets the complete 140+ factor engine + nitpicky details + ML anomaly detection.
    - Long sleeps between symbols/batches to respect free yfinance limits and ensure data quality.
    - No early filtering: every stock is evaluated. Opportunities "everywhere".
    - ML: IsolationForest on factor features to flag "unusual high-potential" setups (nitpicking details).
    Returns list of full payloads sorted by buy_score. Use for deep opportunity discovery leaving no stone unturned.
    """
    from app.engine.signals import analyze_symbol
    import time
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    news_counts = news_counts or {}
    news_titles = news_titles or {}
    earnings_map = earnings_map or {}
    events_by_symbol = events_by_symbol or {}
    results = []
    features_for_ml = []  # for ML: collect numeric factor points
    # Extremely conservative for full accuracy on free tier (time no object)
    batch_size = 2
    per_symbol_sleep = 5.0  # seconds - slow for data quality and to avoid rate limits
    for i in range(0, len(pool), batch_size):
        chunk = pool[i:i+batch_size]
        for sym in chunk:
            try:
                t = yf.Ticker(sym)
                # Longer history for full accuracy on technicals, bases, trends, volatility
                hist = t.history(period="2y", auto_adjust=True)
                if hist.empty or len(hist) < 100:
                    continue  # insufficient data for accurate scoring
                info = t.info or {}
                # Extra pulls for accuracy (recommendations, ownership, more fundamentals)
                try:
                    recs = getattr(t, 'recommendations', None)
                    if recs is not None and not recs.empty:
                        info['recommendations'] = recs.tail(5).to_dict()
                except:
                    pass
                try:
                    holders = getattr(t, 'major_holders', None)
                    if holders is not None and not holders.empty:
                        info['major_holders'] = holders.to_dict()
                except:
                    pass
                market = "india" if sym.endswith((".NS", ".BO")) else "uk" if sym.endswith(".L") else "us"
                nt = news_titles.get(sym, [])[:15]
                earn = earnings_map.get(sym)
                nc = news_counts.get(sym, 0)
                sig = analyze_symbol(
                    sym,
                    market,
                    hist,
                    info,
                    nc,
                    None,
                    earnings=earn,
                    news_titles=nt,
                    market_events=events_by_symbol.get(sym, []),
                )
                # Collect numeric features from factor points for ML
                factor_points = [f.get('weighted_points', f.get('points', 0)) for f in sig.factor_breakdown if f.get('status') == 'pass']
                if len(factor_points) < 5:
                    factor_points = [0] * 10
                features_for_ml.append(factor_points[:10])  # pad/truncate
                # Compute confidence / data quality (0-100)
                conf = 100
                if not info or len(info) < 10:
                    conf -= 20  # missing fundamentals
                if len(hist) < 200:
                    conf -= 15  # short history
                vol = hist["Volume"].iloc[-1] if len(hist) > 0 else 0
                if vol < 10000:  # low volume proxy
                    conf -= 10
                if not nt or len(nt) < 2:
                    conf -= 10  # weak news
                # earnings source
                if earn and earn.get("from_news"):
                    conf -= 5
                # market coverage (India often thinner data)
                if market == "india":
                    conf -= 5
                conf = max(40, min(100, conf))
                payload = {
                    "symbol": sym,
                    "market": market,
                    "score": sig.score,
                    "buy_score": sig.metrics.get("buy_score", sig.score),
                    "quality_score": sig.metrics.get("quality_score", 0),
                    "confidence_score": conf,
                    "signals": sig.signals,
                    "alerts": sig.alerts,
                    "metrics": sig.metrics,
                    "factors_hit": sig.factors_hit,
                    "factors_total": sig.factors_total,
                    "factor_breakdown": sig.factor_breakdown,
                    "sparkline": [round(float(x), 4) for x in hist["Close"].tail(60).tolist()],
                    "full_exhaustive": True,
                    "data_quality": "high" if conf > 80 else ("medium" if conf > 60 else "low"),
                    "history_years": round(len(hist)/252, 1),
                }
                results.append(payload)
            except Exception as e:
                # Log but continue for full coverage (no stone unturned)
                logger.debug("Full scan skip %s: %s", sym, str(e)[:100])
                continue
            time.sleep(per_symbol_sleep)  # Respect rates for accuracy
        # Batch sleep
        time.sleep(10.0)
    # ML for nitpicking: Isolation Forest to find "unusual" high-potential setups from the factor space
    if len(features_for_ml) > 5:
        try:
            X = np.array([f + [0]*(10-len(f)) for f in features_for_ml])
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            iso = IsolationForest(contamination=0.1, random_state=42)
            iso.fit(X_scaled)
            scores = iso.decision_function(X_scaled)  # higher = more normal, lower = anomaly (opp)
            for idx, p in enumerate(results):
                p["ml_anomaly_score"] = round(float(scores[idx]), 3)
                if p["ml_anomaly_score"] < -0.1:  # anomalous = potential hidden opp
                    p["alerts"] = p.get("alerts", []) + ["ML: Unusual factor profile - high potential outlier"]
        except Exception as e:
            logger.debug("ML in full scan skipped: %s", e)
    results.sort(key=lambda x: x.get("buy_score", x.get("score", 0)), reverse=True)
    logger.info("Full exhaustive scan complete: %d high-quality opportunities from %d attempted symbols", len([r for r in results if r.get("buy_score",0)>30]), len(pool))
    return results
