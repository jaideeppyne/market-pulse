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

# Extended liquid India mid/large caps (EMS, defense, power, infra, banks, consumption, auto, metals)
NIFTY_EXTENDED = [
    "DIXON.NS", "KAYNES.NS", "SYRMA.NS", "AMBER.NS", "POLYCAB.NS", "KEI.NS", "CGPOWER.NS",
    "ABB.NS", "SIEMENS.NS", "HAL.NS", "MAZDOCK.NS", "GRSE.NS", "COCHINSHIP.NS", "BHEL.NS",
    "DMART.NS", "PIDILITIND.NS", "HAVELLS.NS", "VOLTAS.NS", "GODREJCP.NS", "INDIGO.NS",
    "IRCTC.NS", "ZOMATO.NS", "PAYTM.NS", "NAUKRI.NS", "MOTHERSON.NS", "TVSMOTOR.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "IDFCFIRSTB.NS", "VEDL.NS", "NMDC.NS",
    "SAIL.NS", "JINDALSTEL.NS", "HINDZINC.NS", "ADANIGREEN.NS", "TATAPOWER.NS", "SUZLON.NS",
    "LUPIN.NS", "AUROPHARMA.NS", "BIOCON.NS", "GLENMARK.NS", "IPCALAB.NS", "ALKEM.NS",
    "PERSISTENT.NS", "LTIM.NS", "MPHASIS.NS", "COFORGE.NS", "LTTS.NS",
    "TATAELXSI.NS", "KPITTECH.NS", "CYIENT.NS", "AFFLE.NS", "HAPPSTMNDS.NS",
    "TATACONSUM.NS", "UBL.NS", "RADICO.NS", "UNITDSPR.NS", "COLPAL.NS", "PGHH.NS",
    "BERGEPAINT.NS", "ASHOKLEY.NS", "BALKRISIND.NS", "MRF.NS", "APOLLOTYRE.NS",
    "JUBLFOOD.NS", "DEVYANI.NS", "WESTLIFE.NS", "SAPPHIRE.NS",
    "LICI.NS", "IRFC.NS", "RVNL.NS", "IRCON.NS", "NBCC.NS", "HUDCO.NS",
    "PFC.NS", "RECLTD.NS", "NHPC.NS", "SJVN.NS", "NH.NS",
    "TATASTEEL.NS", "HINDALCO.NS", "JSWSTEEL.NS", "COALINDIA.NS", "NMDC.NS",
    "HINDCOPPER.NS", "NATIONALUM.NS", "MOIL.NS",
]

# Additional broader India coverage (more large/mid that appear in news/FII flows)
NIFTY_BROADER = [
    "ADANIPORTS.NS", "ADANIENT.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "TATAMTRDVR.NS",
    "M&M.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "TVSMOTOR.NS",
    "MARUTI.NS", "TATAMOTORS.NS", "ASHOKLEY.NS", "ESCORTS.NS",
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS", "INDUSINDBK.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS", "IDFCFIRSTB.NS", "FEDERALBNK.NS",
    "AUBANK.NS", "BANDHANBNK.NS", "RBLBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS",
    "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "COLPAL.NS", "PGHH.NS", "EMAMILTD.NS",
    "SHREECEM.NS", "ULTRACEMCO.NS", "GRASIM.NS", "ACC.NS", "AMBUJACEM.NS",
    "SUNPHARMA.NS", "DRREDDY.NS", "DIVISLAB.NS", "CIPLA.NS", "LUPIN.NS", "AUROPHARMA.NS",
    "APOLLOHOSP.NS", "FORTIS.NS", "MAXHEALTH.NS", "MEDANTA.NS",
    "RELIANCE.NS", "BHARTIARTL.NS", "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
    "LT.NS", "LTIM.NS", "PERSISTENT.NS", "MPHASIS.NS",
    "POWERGRID.NS", "NTPC.NS", "TATAPOWER.NS", "ADANIGREEN.NS", "JSWENERGY.NS",
    "ONGC.NS", "BPCL.NS", "IOC.NS", "GAIL.NS", "IGL.NS", "MGL.NS",
    "TRENT.NS", "AVALON.NS", "ABFRL.NS", "VMART.NS", "CROMPTON.NS",
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

# Much larger practical US coverage for deeper scans (majors + active liquid names across sectors)
# Note: "All listed" US+India is ~8-12k symbols total; liquid/tradable names we can realistically score
# with free yfinance in reasonable time on free hosting is a few thousand high-signal ones.
# The live scanner focuses on "hot" movers from this pool. The Analyze box + /api/analyze runs the
# *identical full 140-factor deep engine* on ANY ticker you type (even outside this list).
US_BROADER = [
    # Tech mega + semi + software/cloud/AI
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","AMD","INTC","QCOM","TXN","AMAT","LRCX","KLAC","SNPS","CDNS","ARM","ASML","TSM","GFS","ON","MRVL","MPWR","TER","ENTG","AMKR","CRUS",
    "NOW","SNOW","DDOG","CRWD","PANW","ZS","NET","ANET","FTNT","CYBR","S","TENB","RBRK","CSCO","ORCL","IBM","ADBE","CRM","INTU","WDAY","TEAM","MDB","PLTR","COIN","HOOD","MSTR","RIOT","MARA",
    "V","MA","AXP","PYPL","SQ","COF","DFS","SYF",
    # Healthcare + biotech + tools
    "LLY","UNH","JNJ","PFE","ABBV","MRK","TMO","DHR","ISRG","REGN","VRTX","GILD","BIIH","AMGN","ILMN","DXCM","IDXX","RMD","HOLX","STE","COO","ALGN","BAX","BDX","EW","ZBH","BSX","SYK","MDT","ABT","BMY",
    # Consumer + retail + auto
    "COST","WMT","TGT","HD","LOW","NKE","SBUX","MCD","YUM","CMG","DPZ","TJX","ROST","LULU","DECK","ONON","ETSY","EBAY","AMZN",
    "TSLA","F","GM","RIVN","LCID","PCAR","ODFL","JBHT","XPO",
    # Energy + industrials + defense + materials
    "XOM","CVX","COP","EOG","MPC","PSX","VLO","SLB","BKR","HAL","OXY","FANG","DVN","APA",
    "GE","RTX","LMT","NOC","GD","HII","LDOS","LHX","BA","CAT","DE","ETN","EMR","ROK","PH","IR","HON","MMM","DOW","DD","LYB","NEM","FCX","ALB","MP","LTHM",
    "UPS","FDX","UNP","CSX","NSC","CP","CNI",
    # Financials + fintech + insurance
    "JPM","BAC","WFC","C","GS","MS","BLK","SCHW","ICE","CME","MCO","SPGI","MSCI","TRV","ALL","PGR","CB","AIG","MET","PRU","AFL",
    # Comm + media + misc growth
    "NFLX","DIS","CMCSA","WBD","PARA","T","VZ","TMUS","CHTR","EA","TTWO","ATVI","RBLX","U","PATH","DOCU","OKTA","TWLO","SMCI","DELL","HPQ","WDC","STX",
    # REITs + utilities + staples for sector completeness
    "AMT","PLD","EQIX","CCI","PSA","O","SPG","WELL","AVB","EQR","DLR","SBAC","WY","VTR",
    "NEE","DUK","SO","D","EXC","XEL","SRE","PEG","ED","WEC","AEP",
    "PG","KO","PEP","PM","MO","CL","KMB","GIS","K","HSY","SJM","CAG","CPB","HRL","MKC","CHD",
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
    """Return {'us': [...], 'india': [...]} symbol lists.

    Reality check on "every listed stock": There are not "few lakhs" (hundreds of thousands)
    of liquid listed companies in US + India combined. Realistic counts for names with
    reasonable float/volume/news flow: US major exchanges ~5-7k, India NSE/BSE active ~2.5-4k.
    Many micro/penny names have almost no data or liquidity.

    Goal: cover the *vast majority of names anyone would actually search or that move on news/FII/earnings*.
    - Live scanner tracks a high-signal subset and ranks "hot" movers using the full engine.
    - The search + Analyze box (and /api/symbol / /api/analyze) runs the *identical deep 140-factor
      engine + smart money + news intel + sector valuation + technicals* on ANY ticker instantly.
      This is how you "scan deep" any name without it being in the hot list.

    To cover even more without missing anything important:
    - Add tickers (one per line) to data/us_extra.txt and data/india_extra.txt — they are loaded automatically.
    - Use the Analyze box for obscure names; it pulls full yfinance fundamentals/history + all
      available news context from the live broad crawlers and still executes the complete algorithm.
    """
    markets = cfg.get("markets", {})
    us: set[str] = set()
    india: set[str] = set()

    if markets.get("us", {}).get("enabled", True):
        ucfg = markets["us"]
        if ucfg.get("use_sp500", True):
            us.update(fetch_sp500_from_wikipedia())
        if ucfg.get("use_nasdaq100", True):
            us.update(NASDAQ_100_SAMPLE)
        # Always include broader liquid names for much deeper market coverage
        us.update(US_BROADER)
        us.update(_read_extra(ROOT / ucfg.get("extra_symbols_file", "data/us_extra.txt")))

    if markets.get("india", {}).get("enabled", True):
        icfg = markets["india"]
        if icfg.get("use_nifty50", True):
            india.update(NIFTY_50)
        if icfg.get("use_nifty500_sample", True):
            india.update(NIFTY_EXTENDED)
            india.update(NIFTY_BROADER)
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