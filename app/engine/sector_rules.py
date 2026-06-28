from __future__ import annotations

from app import company_names

# Yahoo-style sector strings the rest of the engine understands.
_TECH = "Technology"; _FIN = "Financial Services"; _HEALTH = "Healthcare"
_ENERGY = "Energy"; _CYC = "Consumer Cyclical"; _DEF = "Consumer Defensive"
_IND = "Industrials"; _MAT = "Basic Materials"; _UTIL = "Utilities"
_COMM = "Communication Services"; _RE = "Real Estate"

# Compact symbol seed for names a keyword can't resolve (extend freely).
SECTOR_SEED: dict[str, str] = {
    # US
    "AAPL": _TECH, "MSFT": _TECH, "NVDA": _TECH, "AVGO": _TECH, "AMD": _TECH,
    "ORCL": _TECH, "CRM": _TECH, "ADBE": _TECH, "INTC": _TECH, "CSCO": _TECH,
    "AMZN": _CYC, "TSLA": _CYC, "HD": _CYC, "NKE": _CYC, "MCD": _CYC, "SBUX": _CYC,
    "GOOGL": _COMM, "GOOG": _COMM, "META": _COMM, "NFLX": _COMM, "DIS": _COMM,
    "JPM": _FIN, "BAC": _FIN, "WFC": _FIN, "GS": _FIN, "MS": _FIN, "V": _FIN, "MA": _FIN,
    "BRK-B": _FIN, "C": _FIN, "AXP": _FIN, "BLK": _FIN, "SCHW": _FIN,
    "UNH": _HEALTH, "JNJ": _HEALTH, "LLY": _HEALTH, "PFE": _HEALTH, "MRK": _HEALTH, "ABBV": _HEALTH,
    "XOM": _ENERGY, "CVX": _ENERGY, "COP": _ENERGY, "SLB": _ENERGY,
    "WMT": _DEF, "PG": _DEF, "KO": _DEF, "PEP": _DEF, "COST": _DEF,
    "CAT": _IND, "BA": _IND, "GE": _IND, "HON": _IND, "UPS": _IND, "RTX": _IND,
    "NEE": _UTIL, "DUK": _UTIL, "SO": _UTIL,
    # India (NSE)
    "RELIANCE.NS": _ENERGY, "ONGC.NS": _ENERGY, "IOC.NS": _ENERGY, "BPCL.NS": _ENERGY, "GAIL.NS": _UTIL,
    "TCS.NS": _TECH, "INFY.NS": _TECH, "WIPRO.NS": _TECH, "HCLTECH.NS": _TECH, "TECHM.NS": _TECH, "LTIM.NS": _TECH,
    "HDFCBANK.NS": _FIN, "ICICIBANK.NS": _FIN, "SBIN.NS": _FIN, "KOTAKBANK.NS": _FIN, "AXISBANK.NS": _FIN,
    "BAJFINANCE.NS": _FIN, "BAJAJFINSV.NS": _FIN, "ABCAPITAL.NS": _FIN, "SBILIFE.NS": _FIN, "HDFCLIFE.NS": _FIN,
    "SUNPHARMA.NS": _HEALTH, "DRREDDY.NS": _HEALTH, "CIPLA.NS": _HEALTH, "DIVISLAB.NS": _HEALTH, "APOLLOHOSP.NS": _HEALTH,
    "HINDUNILVR.NS": _DEF, "ITC.NS": _DEF, "NESTLEIND.NS": _DEF, "BRITANNIA.NS": _DEF, "TATACONSUM.NS": _DEF, "DABUR.NS": _DEF, "AMBIKCO.NS": _DEF,
    "MARUTI.NS": _CYC, "TATAMOTORS.NS": _CYC, "M&M.NS": _CYC, "BAJAJ-AUTO.NS": _CYC, "EICHERMOT.NS": _CYC, "HEROMOTOCO.NS": _CYC,
    "TITAN.NS": _CYC, "TRENT.NS": _CYC, "ADVANIHOTR.NS": _CYC, "TVSSRICHAK.NS": _CYC,
    "LT.NS": _IND, "3MINDIA.NS": _IND, "SIEMENS.NS": _IND, "ABB.NS": _IND, "BEL.NS": _IND, "HAL.NS": _IND, "ACCURACY.NS": _IND,
    "TATASTEEL.NS": _MAT, "JSWSTEEL.NS": _MAT, "HINDALCO.NS": _MAT, "ULTRACEMCO.NS": _MAT, "GRASIM.NS": _MAT, "ASIANPAINT.NS": _MAT,
    "NTPC.NS": _UTIL, "POWERGRID.NS": _UTIL, "TATAPOWER.NS": _UTIL,
    "BHARTIARTL.NS": _COMM, "DLF.NS": _RE,
    # UK
    "BLND.L": _RE, "BARC.L": _FIN, "HSBA.L": _FIN, "LLOY.L": _FIN, "BP.L": _ENERGY, "SHEL.L": _ENERGY,
    "VOD.L": _COMM, "GSK.L": _HEALTH, "AZN.L": _HEALTH, "ULVR.L": _DEF,
}

# Company-name keyword -> sector. Order matters (first hit wins); checked on the
# learned company name, so it generalises to the long tail of small/mid caps.
_NAME_RULES: list[tuple[tuple[str, ...], str]] = [
    (("bank", "finserv", "financ", "capital", "investment", "securities", "broking",
      "insurance", "life insur", "mutual", "nbfc", "housing finance", "credit", "fintech"), _FIN),
    (("pharma", "healthcare", "hospital", "labs", "laborat*", "life science", "biotech",
      "diagnost", "drugs", "medical", "wellness", "remedies"), _HEALTH),
    (("software", "technolog", "infotech", "info tech", "infosys", "systems", "digital",
      "computer", "cyber", "data", "cloud", "semiconductor", "electronics", "it services"), _TECH),
    (("motor", "auto", "automobile", "tyre", "tyres", "vehicle", "bearings"), _CYC),
    (("hotel", "resort", "retail", "apparel", "textile", "garment", "footwear", "jewell",
      "leisure", "entertainment", "media", "restaurant", "consumer durable", "appliance"), _CYC),
    (("foods", "food", "beverage", "dairy", "sugar", "agro", "fmcg", "consumer products",
      "tea", "coffee", "nestle", "tobacco", "breweries", "distiller"), _DEF),
    (("oil", "gas", "petroleum", "energy", "refiner", "coal", "drilling"), _ENERGY),
    (("power", "electric", "utilit", "transmission", "grid"), _UTIL),
    (("steel", "cement", "metal", "aluminium", "aluminum", "mining", "chemical", "fertiliz",
      "fertiliser", "paints", "polymer", "plastic", "copper", "zinc"), _MAT),
    (("infra", "construction", "engineer", "industri", "capital goods", "machinery", "tools",
      "defence", "defense", "aerospace", "shipping", "ports", "logistics", "railway", "cargo",
      "equipment", "manufactur"), _IND),
    (("telecom", "communication", "media", "broadcast", "network", "airtel"), _COMM),
    (("realty", "real estate", "estate", "properties", "developers", "infraestate", "land"), _RE),
]


def resolve_sector(symbol: str, market: str = "us") -> str:
    """Best-effort Yahoo-style sector without live yfinance info.

    Resolution order: static symbol seed -> company-name keyword heuristic -> "".
    Free, offline, deterministic.
    """
    if not symbol:
        return ""
    sym = symbol.upper()
    seeded = SECTOR_SEED.get(sym)
    if seeded:
        return seeded
    name = (company_names.name_for(sym) or "").lower()
    if name and name != sym.lower():
        for keys, sector in _NAME_RULES:
            for k in keys:
                k2 = k.rstrip("*")
                if k2 in name:
                    return sector
    return ""


def sector_bucket(sector: str | None, industry: str | None, market: str) -> str:
    s = (sector or "").lower()
    i = (industry or "").lower()
    text = f"{s} {i}"
    if "bank" in text or "financial services" in s and "insurance" not in text:
        return "banks"
    if "insurance" in text or "insur" in i:
        return "insurance"
    if "real estate" in text or "reit" in text:
        return "real_estate"
    if "utility" in text or "utilities" in s:
        return "utilities"
    if "energy" in s or "oil" in i or "gas" in i:
        return "energy"
    if "technology" in s or "software" in i or "semiconductor" in i:
        return "technology"
    if "health" in s or "pharma" in i or "biotech" in i:
        return "healthcare"
    if "consumer" in s:
        return "consumer"
    if "industrial" in s or "defence" in i or "defense" in i:
        return "industrials"
    if market == "india" and any(
        x in text for x in ("defence", "defense", "ship", "aerospace", "government")
    ):
        return "india_defense_psu"
    return "general"


def pe_pb_thresholds(bucket: str, market: str) -> dict[str, float]:
    """Sector-aware valuation bands (rough defaults)."""
    base = {
        "pe_low": 5,
        "pe_high": 35,
        "pb_low": 0.5,
        "pb_high": 5.0,
        "prefer_pb_over_pe": False,
    }
    overrides = {
        "banks": {"pe_low": 4, "pe_high": 18, "pb_low": 0.6, "pb_high": 3.5, "prefer_pb_over_pe": True},
        "insurance": {"pe_low": 6, "pe_high": 22, "prefer_pb_over_pe": True},
        "real_estate": {"pe_high": 30, "pb_high": 4, "prefer_pb_over_pe": True},
        "technology": {"pe_high": 55, "pb_high": 12, "prefer_pb_over_pe": False},
        "healthcare": {"pe_high": 45, "prefer_pb_over_pe": False},
        "utilities": {"pe_high": 22, "dividend_focus": True},
        "energy": {"pe_high": 15, "pb_high": 2.5},
        "india_defense_psu": {"pe_high": 50, "pb_high": 8},
    }
    out = dict(base)
    out.update(overrides.get(bucket, {}))
    if market == "india":
        out["pe_high"] = out.get("pe_high", 35) * 1.15
    return out