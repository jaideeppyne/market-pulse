from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# Nifty 50 (NSE symbols with .NS suffix for yfinance)
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "HINDUNILVR.NS",
    "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS",
    "ASIANPAINT.NS", "MARUTI.NS", "TITAN.NS", "BAJFINANCE.NS", "HCLTECH.NS", "WIPRO.NS",
    "ULTRACEMCO.NS", "SUNPHARMA.NS", "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "NESTLEIND.NS",
    "TATAMOTORS.NS", "M&M.NS", "ADANIENT.NS", "ADANIPORTS.NS", "JSWSTEEL.NS", "TATASTEEL.NS",
    "TECHM.NS", "INDUSINDBK.NS", "BAJAJFINSV.NS", "HINDALCO.NS", "COALINDIA.NS", "GRASIM.NS",
    "DIVISLAB.NS", "CIPLA.NS", "DRREDDY.NS", "APOLLOHOSP.NS", "EICHERMOT.NS", "BPCL.NS",
    "HEROMOTOCO.NS", "BRITANNIA.NS", "TRENT.NS", "SHRIRAMFIN.NS", "SBILIFE.NS", "HDFCLIFE.NS",
    "BEL.NS", "ETERNAL.NS",
]

# Extended liquid India mid/large caps (EMS, defense, power, infra)
NIFTY_EXTENDED = [
    "DIXON.NS", "KAYNES.NS", "SYRMA.NS", "AMBER.NS", "POLYCAB.NS", "KEI.NS", "CGPOWER.NS",
    "ABB.NS", "SIEMENS.NS", "HAL.NS", "MAZDOCK.NS", "GRSE.NS", "COCHINSHIP.NS", "BHEL.NS",
    "DMART.NS", "PIDILITIND.NS", "HAVELLS.NS", "VOLTAS.NS", "GODREJCP.NS", "INDIGO.NS",
    "IRCTC.NS", "ZOMATO.NS", "PAYTM.NS", "NAUKRI.NS", "MOTHERSON.NS", "TVSMOTOR.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "IDFCFIRSTB.NS", "VEDL.NS", "NMDC.NS",
    "SAIL.NS", "JINDALSTEL.NS", "HINDZINC.NS", "ADANIGREEN.NS", "TATAPOWER.NS", "SUZLON.NS",
]

NASDAQ_100_SAMPLE = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "PEP", "CSCO", "INTC", "CMCSA", "QCOM", "TXN", "AMGN",
    "HON", "AMAT", "INTU", "BKNG", "ISRG", "VRTX", "ADP", "SBUX", "GILD", "REGN",
    "PANW", "MU", "LRCX", "MDLZ", "ADI", "KLAC", "SNPS", "CDNS", "MELI", "PYPL",
    "CRWD", "MAR", "FTNT", "ORLY", "CSX", "ABNB", "DASH", "WDAY", "MNST", "CTAS",
    "PCAR", "ROP", "NXPI", "AEP", "CHTR", "PAYX", "MRVL", "FAST", "ROST", "KDP",
    "EA", "VRSK", "EXC", "XEL", "CCEP", "BKR", "FANG", "ODFL", "GEHC", "LULU",
    "KHC", "CSGP", "DDOG", "TTD", "ON", "BIIB", "ANSS", "CDW", "GFS", "MDB",
    "ARM", "SMCI", "COIN", "PLTR", "HOOD", "RDDT", "VRT", "GEV", "TTAN", "AGX",
    # More liquid names for better fallback coverage
    "INTC", "PYPL", "SIRI", "WBD", "DXCM", "BKR", "ODFL", "CPRT", "KDP", "MCHP",
    "ILMN", "IDXX", "RMD", "MTD", "TECH", "WST", "STE", "COO", "HOLX", "ALGN",
]

SP500_SAMPLE = [
    "JPM", "V", "MA", "UNH", "JNJ", "PG", "HD", "CVX", "MRK", "ABBV",
    "LLY", "BAC", "WMT", "XOM", "CRM", "ORCL", "ACN", "MCD", "CAT", "IBM",
    "GE", "RTX", "LMT", "NOC", "GD", "DE", "ETN", "EME", "PWR", "FIX",
    "NOW", "SNOW", "ZS", "NET", "ANET", "CLS", "TSM", "ASML", "SOXX",
    # Expanded static fallback (used when Wikipedia scrape fails, e.g. missing lxml)
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "PEP", "CSCO", "INTC", "QCOM", "TXN", "AMGN", "HON",
    "AMAT", "INTU", "BKNG", "ISRG", "VRTX", "ADP", "SBUX", "GILD", "REGN", "PANW",
    "MU", "LRCX", "MDLZ", "ADI", "KLAC", "SNPS", "CDNS", "MELI", "PYPL", "CRWD",
    "MAR", "FTNT", "ORLY", "CSX", "ABNB", "DASH", "WDAY", "MNST", "CTAS", "PCAR",
    "ROP", "NXPI", "AEP", "CHTR", "PAYX", "MRVL", "FAST", "ROST", "KDP", "EA",
    "VRSK", "EXC", "XEL", "CCEP", "BKR", "FANG", "ODFL", "GEHC", "LULU", "KHC",
    "CSGP", "DDOG", "TTD", "ON", "BIIB", "ANSS", "CDW", "GFS", "MDB", "ARM",
    "SMCI", "COIN", "PLTR", "HOOD", "VRT", "GEV", "TTAN", "AGX", "RDW", "OSCR",
    "JNJ", "PFE", "ABT", "TMO", "DHR", "BMY", "AMT", "PLD", "CCI", "EQIX",
    "SPG", "O", "PSA", "WELL", "AVB", "EQR", "DLR", "SBAC", "WY", "VTR",
]


def _read_extra(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().upper()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def fetch_sp500_from_wikipedia() -> list[str]:
    """Try live Wikipedia list (requires lxml in env). Falls back to expanded static sample."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            storage_options={"User-Agent": "MarketPulse/1.0 (+https://local/market-pulse)"},
            flavor="lxml",
        )
        df = tables[0]
        col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        syms = df[col].astype(str).str.replace(".", "-", regex=False).tolist()
        if len(syms) > 50:
            return syms
    except Exception as e:
        # Common cause: missing lxml (add to requirements + recreate .venv)
        # or network / parser issues. Fall back silently to larger static list.
        pass
    # Always return at least the expanded static sample so universe is never tiny
    return SP500_SAMPLE


def build_universe(cfg: dict) -> dict[str, list[str]]:
    """Return {'us': [...], 'india': [...]} symbol lists."""
    markets = cfg.get("markets", {})
    us: set[str] = set()
    india: set[str] = set()

    if markets.get("us", {}).get("enabled", True):
        ucfg = markets["us"]
        if ucfg.get("use_sp500", True):
            us.update(fetch_sp500_from_wikipedia())
        if ucfg.get("use_nasdaq100", True):
            us.update(NASDAQ_100_SAMPLE)
        us.update(_read_extra(ROOT / ucfg.get("extra_symbols_file", "data/us_extra.txt")))

    if markets.get("india", {}).get("enabled", True):
        icfg = markets["india"]
        if icfg.get("use_nifty50", True):
            india.update(NIFTY_50)
        if icfg.get("use_nifty500_sample", True):
            india.update(NIFTY_EXTENDED)
        india.update(_read_extra(ROOT / icfg.get("extra_symbols_file", "data/india_extra.txt")))

    # Normalize India symbols
    india_norm = set()
    for s in india:
        s = s.upper()
        if not s.endswith(".NS") and not s.endswith(".BO"):
            s = f"{s}.NS"
        india_norm.add(s)

    return {
        "us": sorted(us),
        "india": sorted(india_norm),
    }


def extract_tickers_from_text(text: str, universe: set[str]) -> list[str]:
    """Match $TICKER, (TICKER), or known symbols (word or parenthesized) in headline/summary.
    Helps with Google News, press releases, etc. that often write "Apple (AAPL)" or "Reliance: ".
    """
    found: set[str] = set()
    up = text.upper()
    # $TICKER or (TICKER) or TICKER:
    for m in re.finditer(r"[\$\(]([A-Z]{1,5})[\)\:]?\b", up):
        t = m.group(1)
        if t in universe:
            found.add(t)
    for sym in universe:
        base = sym.replace(".NS", "").replace(".BO", "")
        if len(base) >= 3 and re.search(rf"\b{re.escape(base)}\b", up):
            found.add(sym)
    return sorted(found)