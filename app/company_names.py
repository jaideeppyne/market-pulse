"""Persistent symbol -> company-name store.

Yahoo/Stooq don't always return a company name (rate limits, Stooq has none),
which made the UI show the ticker twice. This module records names whenever
provider info IS available, persists them, and serves a best-effort name for
any symbol (live info -> learned store -> static seed -> symbol).
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_STORE = Path(os.getenv("COMPANY_NAMES_PATH", _ROOT / "data" / "company_names.json"))
# Large committed static map (ticker -> full company name) loaded at import; fills gaps
# UNDER any runtime-learned/live name (learned wins, seed only fills missing).
_SEED_FILE = Path(os.getenv("COMPANY_NAMES_SEED_PATH", _ROOT / "data" / "company_names_seed.json"))

# Seed so the most common US + India names render instantly on a cold start.
_SEED: dict[str, str] = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation", "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.", "GOOGL": "Alphabet Inc.", "GOOG": "Alphabet Inc.",
    "META": "Meta Platforms, Inc.", "TSLA": "Tesla, Inc.", "AVGO": "Broadcom Inc.",
    "BRK-B": "Berkshire Hathaway Inc.", "JPM": "JPMorgan Chase & Co.", "V": "Visa Inc.",
    "MA": "Mastercard Incorporated", "UNH": "UnitedHealth Group", "XOM": "Exxon Mobil Corporation",
    "JNJ": "Johnson & Johnson", "WMT": "Walmart Inc.", "PG": "Procter & Gamble",
    "HD": "The Home Depot, Inc.", "NFLX": "Netflix, Inc.", "AMD": "Advanced Micro Devices",
    "INTC": "Intel Corporation", "CRM": "Salesforce, Inc.", "ORCL": "Oracle Corporation",
    "ADBE": "Adobe Inc.", "PEP": "PepsiCo, Inc.", "KO": "The Coca-Cola Company",
    "CSCO": "Cisco Systems, Inc.", "QCOM": "QUALCOMM Incorporated", "TXN": "Texas Instruments",
    "BAC": "Bank of America", "DIS": "The Walt Disney Company", "PFE": "Pfizer Inc.",
    "RELIANCE.NS": "Reliance Industries Limited", "TCS.NS": "Tata Consultancy Services",
    "HDFCBANK.NS": "HDFC Bank Limited", "INFY.NS": "Infosys Limited",
    "ICICIBANK.NS": "ICICI Bank Limited", "SBIN.NS": "State Bank of India",
    "BHARTIARTL.NS": "Bharti Airtel Limited", "ITC.NS": "ITC Limited",
    "LT.NS": "Larsen & Toubro Limited", "KOTAKBANK.NS": "Kotak Mahindra Bank",
    "HINDUNILVR.NS": "Hindustan Unilever Limited", "BAJFINANCE.NS": "Bajaj Finance Limited",
    "ASIANPAINT.NS": "Asian Paints Limited", "MARUTI.NS": "Maruti Suzuki India",
    "AXISBANK.NS": "Axis Bank Limited", "TATAMOTORS.NS": "Tata Motors Limited",
    "SUNPHARMA.NS": "Sun Pharmaceutical", "TITAN.NS": "Titan Company Limited",
    "WIPRO.NS": "Wipro Limited", "ADANIENT.NS": "Adani Enterprises Limited",
    "M&M.NS": "Mahindra & Mahindra", "NTPC.NS": "NTPC Limited", "POWERGRID.NS": "Power Grid Corporation",
    "ULTRACEMCO.NS": "UltraTech Cement", "NESTLEIND.NS": "Nestlé India Limited",
}

_lock = threading.Lock()
_names: dict[str, str] = {}
_loaded = False
_dirty = False
_last_save = 0.0
_SAVE_INTERVAL = 25.0


def _load_seed_file() -> dict[str, str]:
    """Large committed static ticker->name map (data/company_names_seed.json).

    Optional file; safe if missing/corrupt. Returns upper-cased mapping.
    """
    try:
        if _SEED_FILE.exists():
            raw = json.loads(_SEED_FILE.read_text(encoding="utf-8")) or {}
            return {str(k).upper(): str(v) for k, v in raw.items() if v}
    except Exception:
        pass
    return {}


def _load() -> None:
    global _loaded
    if _loaded:
        return
    data: dict[str, str] = {}
    try:
        if _STORE.exists():
            data = json.loads(_STORE.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    # Precedence (low -> high): big static seed file < inline _SEED < learned store.
    # Runtime-learned / live names always win; the seed only fills gaps.
    merged: dict[str, str] = {}
    merged.update(_load_seed_file())
    merged.update(_SEED)
    merged.update({str(k).upper(): str(v) for k, v in data.items() if v})
    with _lock:
        _names.update(merged)
        _loaded = True


def _looks_like_name(name: str, symbol: str) -> bool:
    n = (name or "").strip()
    if not n or len(n) < 2:
        return False
    if n.upper() == (symbol or "").upper():
        return False
    if n.upper().replace(".NS", "").replace(".BO", "").replace(".L", "") == (symbol or "").upper().replace(".NS", "").replace(".BO", "").replace(".L", ""):
        return False
    return True


def _extract(info: dict[str, Any] | None) -> str:
    if not info:
        return ""
    for key in ("longName", "shortName", "displayName"):
        v = str(info.get(key) or "").strip()
        if v:
            return v
    return ""


def record(symbol: str, info: dict[str, Any] | None) -> None:
    """Learn a name from provider info if it's a real company name."""
    _load()
    if not symbol:
        return
    name = _extract(info)
    sym = symbol.upper()
    if not _looks_like_name(name, sym):
        return
    global _dirty
    with _lock:
        if _names.get(sym) != name:
            _names[sym] = name
            _dirty = True
    _maybe_save()


def name_for(symbol: str, info: dict[str, Any] | None = None) -> str:
    """Best-effort full company name. Records from info as a side effect."""
    if not symbol:
        return symbol
    sym = symbol.upper()
    live = _extract(info)
    if _looks_like_name(live, sym):
        record(sym, info)
        return live
    _load()
    with _lock:
        return _names.get(sym) or symbol


def _maybe_save(force: bool = False) -> None:
    global _last_save, _dirty
    now = time.time()
    if not force and (not _dirty or now - _last_save < _SAVE_INTERVAL):
        return
    with _lock:
        snapshot = dict(_names)
        _dirty = False
        _last_save = now
    try:
        _STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STORE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_STORE)
    except Exception:
        pass
