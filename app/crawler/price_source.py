"""Thin, isolated data-resilience layer for price/fundamental fetches.

yfinance is the single point of failure for every price + fundamental pull in the
scanner. This module wraps the yfinance batch download so that:

  * exceptions and empty responses are caught and never crash the scan loop,
  * failures are logged and surfaced via a module-level health snapshot
    (``get_source_health()``), and
  * when a primary fetch fails/returns empty for a symbol, an optional secondary
    source (Stooq daily CSV, no API key, plain HTTP) is tried for *prices* so the
    technical engine still has an OHLCV history to score.

It is intentionally minimal and dependency-light: it reuses the column
normalisation already used by the price crawler and only reaches for Stooq when
yfinance comes back empty. If the network is unavailable, every call degrades
gracefully to an empty frame and a recorded "error"/"empty" health state.
"""
from __future__ import annotations

import io
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Health tracking (surfaced via /api health or status fields by other agents).
# ---------------------------------------------------------------------------
_health_lock = threading.Lock()
_health: dict[str, Any] = {
    "yfinance": {"ok": None, "last_ok": None, "last_error": None, "consecutive_failures": 0},
    "stooq": {"ok": None, "last_ok": None, "last_error": None, "fallback_used": 0},
    "last_batch": {"requested": 0, "yf_hits": 0, "stooq_hits": 0, "ts": None},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(source: str, ok: bool, error: str | None = None) -> None:
    with _health_lock:
        h = _health.setdefault(
            source, {"ok": None, "last_ok": None, "last_error": None, "consecutive_failures": 0}
        )
        h["ok"] = ok
        if ok:
            h["last_ok"] = _now()
            h["consecutive_failures"] = 0
        else:
            h["last_error"] = (error or "")[:200]
            h["consecutive_failures"] = int(h.get("consecutive_failures", 0)) + 1


def get_source_health() -> dict[str, Any]:
    """Return a copy of the current data-source health snapshot."""
    with _health_lock:
        # shallow copy of nested dicts so callers can't mutate internal state
        return {k: dict(v) for k, v in _health.items()}


# ---------------------------------------------------------------------------
# Secondary source: Stooq daily CSV (prices only). No key, plain HTTP GET.
# ---------------------------------------------------------------------------
def _stooq_symbol(sym: str) -> str | None:
    """Map a yfinance ticker to a Stooq ticker. Returns None if unsupported.

    Stooq uses lowercase and ``.us`` for US tickers; Indian/UK suffixes aren't
    reliably covered, so we only attempt plain US symbols (best-effort fallback).
    """
    s = sym.strip().lower()
    if not s or any(s.endswith(suf) for suf in (".ns", ".bo", ".l")):
        return None
    if "." in s:  # other exchange suffixes we don't map
        return None
    return f"{s}.us"


def _fetch_stooq_history(sym: str, timeout: float = 8.0) -> pd.DataFrame:
    """Fetch daily OHLCV from Stooq CSV. Returns empty frame on any failure."""
    stq = _stooq_symbol(sym)
    if not stq:
        return pd.DataFrame()
    url = f"https://stooq.com/q/d/l/?s={stq}&i=d"
    try:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (market-pulse)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", "replace")
        if not raw or raw.lower().startswith("<") or "no data" in raw.lower():
            _record("stooq", False, "empty/no-data")
            return pd.DataFrame()
        df = pd.read_csv(io.StringIO(raw))
        if df.empty or "Close" not in df.columns:
            _record("stooq", False, "no Close column")
            return pd.DataFrame()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"]).set_index("Date")
        # Keep only standard OHLCV columns the engine expects.
        keep = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
        df = df[keep].dropna(how="all")
        if df.empty:
            _record("stooq", False, "empty after clean")
            return pd.DataFrame()
        _record("stooq", True)
        with _health_lock:
            _health["stooq"]["fallback_used"] = int(_health["stooq"].get("fallback_used", 0)) + 1
        return df
    except Exception as e:  # network down, parse error, etc.
        _record("stooq", False, str(e))
        logger.debug("Stooq fallback failed for %s: %s", sym, str(e)[:120])
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Primary entry point used by the price crawler.
# ---------------------------------------------------------------------------
def fetch_batch_resilient(
    symbols: list[str],
    primary_fetch: Callable[[list[str]], dict[str, tuple[pd.DataFrame, dict, dict | None]]],
    enable_fallback: bool = True,
) -> dict[str, tuple[pd.DataFrame, dict, dict | None]]:
    """Run the primary (yfinance) batch fetch with error isolation + Stooq fallback.

    ``primary_fetch`` is injected (the crawler's existing ``_fetch_batch``) so this
    module stays decoupled from yfinance specifics and is easy to unit-test offline.
    Never raises: on total failure it returns whatever it could gather (possibly {}).
    """
    if not symbols:
        return {}

    out: dict[str, tuple[pd.DataFrame, dict, dict | None]] = {}
    try:
        out = primary_fetch(symbols) or {}
        _record("yfinance", True)
    except Exception as e:
        _record("yfinance", False, str(e))
        logger.warning("Primary (yfinance) batch fetch failed for %d symbols: %s", len(symbols), str(e)[:160])
        out = {}

    yf_hits = len(out)
    stooq_hits = 0
    if enable_fallback:
        missing = [s for s in symbols if s not in out]
        for sym in missing:
            df = _fetch_stooq_history(sym)
            if df is not None and not df.empty and len(df) >= 10:
                # Match the (history, info, calendar) tuple shape the crawler expects.
                out[sym] = (df, {"_source": "stooq"}, None)
                stooq_hits += 1

    with _health_lock:
        _health["last_batch"] = {
            "requested": len(symbols),
            "yf_hits": yf_hits,
            "stooq_hits": stooq_hits,
            "ts": _now(),
        }
    if yf_hits == 0 and stooq_hits == 0:
        logger.warning("All data sources empty for batch of %d symbols", len(symbols))
    return out


# ---------------------------------------------------------------------------
# Tertiary source: Yahoo v8 chart endpoint (no crumb). Works for ANY market.
# ---------------------------------------------------------------------------
def _fetch_yahoo_chart_one(sym: str, timeout: float = 9.0):
    """No-crumb daily OHLCV via Yahoo's chart endpoint.

    yfinance's fundamentals use the crumb-protected quoteSummary endpoint, which
    gets rate-limited from datacenter IPs ('Invalid Crumb'). The chart endpoint
    usually still serves OHLCV with just a browser User-Agent, and it covers every
    market (US / .NS / .BO / .L) -- so it backstops India/UK where Stooq has none.
    Returns (history_df, info, None) or None.
    """
    import json as _json
    import urllib.parse
    import urllib.request

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(sym)
        + "?range=6mo&interval=1d&includePrePost=false"
    )
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = _json.loads(resp.read().decode("utf-8", "replace"))
        result = (((data or {}).get("chart") or {}).get("result") or [])
        if not result:
            _record("yahoo_chart", False, "no result")
            return None
        r0 = result[0]
        ts = r0.get("timestamp") or []
        quote = (((r0.get("indicators") or {}).get("quote") or [{}])[0])
        closes = quote.get("close") or []
        if not ts or not closes:
            _record("yahoo_chart", False, "no quotes")
            return None
        df = pd.DataFrame({
            "Open": quote.get("open"), "High": quote.get("high"),
            "Low": quote.get("low"), "Close": closes, "Volume": quote.get("volume"),
        })
        df.index = pd.to_datetime(pd.Series(ts), unit="s", errors="coerce")
        df = df.dropna(subset=["Close"])
        if df.empty or len(df) < 10:
            _record("yahoo_chart", False, "insufficient")
            return None
        meta = r0.get("meta") or {}
        info = {
            "_source": "yahoo_chart",
            "symbol": meta.get("symbol") or sym,
            "currency": meta.get("currency"),
            "exchange": meta.get("exchangeName") or meta.get("fullExchangeName"),
            "fullExchangeName": meta.get("fullExchangeName"),
            "quoteType": meta.get("instrumentType"),
            "regularMarketPrice": meta.get("regularMarketPrice"),
            "shortName": meta.get("shortName"),
            "longName": meta.get("longName"),
        }
        _record("yahoo_chart", True)
        return (df, info, None)
    except Exception as e:
        _record("yahoo_chart", False, str(e))
        logger.debug("Yahoo chart fallback failed for %s: %s", sym, str(e)[:120])
        return None


def fetch_yahoo_chart_batch(symbols: list[str]) -> dict[str, tuple]:
    out: dict[str, tuple] = {}
    for sym in symbols:
        hit = _fetch_yahoo_chart_one(sym)
        if hit is not None:
            out[sym] = hit
    return out


# ---------------------------------------------------------------------------
# Company-name resolution via Yahoo chart meta (no crumb). One call per symbol,
# but results are cached forever by the caller, so steady-state cost is ~zero.
# ---------------------------------------------------------------------------
def fetch_name_one(sym: str, timeout: float = 6.0) -> str:
    """Return a company name for sym from Yahoo chart meta, or '' on failure."""
    import json as _json
    import urllib.parse
    import urllib.request
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(sym)
        + "?range=5d&interval=1d"
    )
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = _json.loads(resp.read().decode("utf-8", "replace"))
        result = (((data or {}).get("chart") or {}).get("result") or [])
        if not result:
            return ""
        meta = result[0].get("meta") or {}
        return str(meta.get("longName") or meta.get("shortName") or "").strip()
    except Exception:
        return ""


def fetch_names_batch(symbols: list[str], max_workers: int = 6) -> dict[str, str]:
    """Concurrently resolve company names for a small batch. Returns only hits."""
    out: dict[str, str] = {}
    if not symbols:
        return out
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for sym, name in zip(symbols, ex.map(fetch_name_one, symbols)):
            if name:
                out[sym] = name
    return out
