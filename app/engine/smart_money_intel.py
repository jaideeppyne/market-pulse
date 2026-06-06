"""
Detect named investors, politicians, and foreign funds buying stocks from headlines.
High-weight factors in factor_registry consume these matches.

Extend INVESTOR_REGISTRY when you find new tracked names in news.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_EXTRA_FILE = Path(__file__).resolve().parents[2] / "data" / "smart_money_extra.txt"

# Must appear in same headline (or nearby line) as the investor name
BUY_CONTEXT = re.compile(
    r"\b("
    r"buy|buys|bought|buying|purchase|purchased|accumulat|"
    r"stake|disclosure|adds|added|raises?\s+holding|increases?\s+position|"
    r"builds?\s+position|enters?|entry|picked|picks|portfolio|"
    r"shareholding|shareholder|promoter|bulk\s+deal|block\s+deal|"
    r"takes\s+stake|ups\s+stake|open\s+market|"
    r"congress.*(buy|purchase|trade)|stock\s+act|"
    r"13f|form\s+4|insider"
    r")\b",
    re.I,
)

# India: top tracked retail / PMS / MF legends (user-requested + widely followed)
INDIA_LEGENDS: list[dict[str, Any]] = [
    {"id": "madhusudan_kela", "name": "Madhusudan Kela", "rx": r"madhusudan\s+kela|mk\s+kela|kela\s+fund"},
    {"id": "ashish_kacholia", "name": "Ashish Kacholia", "rx": r"ashish\s+kacholia|kacholia"},
    {"id": "vijay_kedia", "name": "Vijay Kedia", "rx": r"vijay\s+kedia"},
    {"id": "raakesh_jhunjhunwala", "name": "Raakesh Jhunjhunwala", "rx": r"raakesh\s+jhunjhunwala|rakesh\s+jhunjhunwala|jhunjhunwala"},
    {"id": "radhakishan_damani", "name": "Radhakishan Damani", "rx": r"radhakishan\s+damani|rk\s+damani|damani"},
    {"id": "dolly_khanna", "name": "Dolly Khanna", "rx": r"dolly\s+khanna|rajiv\s+khanna"},
    {"id": "porinju_veliyath", "name": "Porinju Veliyath", "rx": r"porinju|veliyath"},
    {"id": "shankar_sharma", "name": "Shankar Sharma", "rx": r"shankar\s+sharma|first\s+dubai"},
    {"id": "nemish_shah", "name": "Nemish Shah", "rx": r"nemish\s+shah|enam"},
    {"id": "sunil_singhania", "name": "Sunil Singhania", "rx": r"sunil\s+singhania|abakkus"},
    {"id": "kenneth_andrade", "name": "Kenneth Andrade", "rx": r"kenneth\s+andrade|old\s+bridge"},
    {"id": "saurabh_mukherjea", "name": "Saurabh Mukherjea", "rx": r"saurabh\s+mukherjea|marcellus"},
    {"id": "amitabh_dayal", "name": "Amitabh Dayal", "rx": r"amitabh\s+dayal"},
    {"id": "ramdeo_agrawal", "name": "Ramdeo Agrawal", "rx": r"ramdeo\s+agrawal|motilal\s+oswal"},
    {"id": "amit_jain", "name": "Amit Jain (Greenshoe)", "rx": r"amit\s+jain.*greenshoe|greenshoe"},
    {"id": "harsh_gupta", "name": "Harsh Gupta", "rx": r"harsh\s+gupta.*marcellus"},
    {"id": "dalal_street", "name": "Dalal Street investor", "rx": r"dalal\s+street.*(buy|stake|accumulat)", "require_buy": False},
]

# US: whales, activists, top funds
US_LEGENDS: list[dict[str, Any]] = [
    {"id": "warren_buffett", "name": "Warren Buffett", "rx": r"warren\s+buffett|berkshire\s+hathaway|berkshire"},
    {"id": "bill_ackman", "name": "Bill Ackman", "rx": r"bill\s+ackman|pershing\s+square"},
    {"id": "carl_icahn", "name": "Carl Icahn", "rx": r"carl\s+icahn|icahn\s+enterprises"},
    {"id": "ray_dalio", "name": "Ray Dalio", "rx": r"ray\s+dalio|bridgewater"},
    {"id": "cathie_wood", "name": "Cathie Wood", "rx": r"cathie\s+wood|ark\s+invest|arkk"},
    {"id": "stanley_druckenmiller", "name": "Stanley Druckenmiller", "rx": r"stanley\s+druckenmiller|druckenmiller"},
    {"id": "david_tepper", "name": "David Tepper", "rx": r"david\s+tepper|appaloosa"},
    {"id": "daniel_loeb", "name": "Daniel Loeb", "rx": r"daniel\s+loeb|third\s+point"},
    {"id": "seth_klarman", "name": "Seth Klarman", "rx": r"seth\s+klarman|baupost"},
    {"id": "paul_tudor_jones", "name": "Paul Tudor Jones", "rx": r"paul\s+tudor\s+jones"},
    {"id": "michael_burry", "name": "Michael Burry", "rx": r"michael\s+burry|scion\s+asset"},
    {"id": "george_soros", "name": "George Soros", "rx": r"george\s+soros|soros\s+fund"},
    {"id": "tiger_global", "name": "Tiger Global", "rx": r"tiger\s+global"},
    {"id": "coatue", "name": "Coatue", "rx": r"coatue\s+management|coatue"},
    {"id": "softbank", "name": "SoftBank / Masa", "rx": r"softbank|masayoshi\s+son"},
    {"id": "blackrock", "name": "BlackRock", "rx": r"blackrock|larry\s+fink"},
    {"id": "vanguard", "name": "Vanguard", "rx": r"vanguard\s+group"},
    {"id": "fidelity", "name": "Fidelity", "rx": r"fidelity\s+investments|fidelity\s+management"},
]

# Politicians & govt disclosures (high attention)
POLITICIANS_US: list[dict[str, Any]] = [
    {"id": "nancy_pelosi", "name": "Nancy Pelosi", "rx": r"nancy\s+pelosi|pelosi"},
    {"id": "congress_trading", "name": "US Congress trade", "rx": r"congress(man|woman|ional).*(stock|trade|buy|purchase)|senator.*(buy|purchase|stock)|house\s+member.*stock", "require_buy": False},
    {"id": "stock_act", "name": "STOCK Act disclosure", "rx": r"stock\s+act|congressional\s+trading|capitol\s+trades", "require_buy": False},
    {"id": "josh_gottheimer", "name": "Josh Gottheimer", "rx": r"josh\s+gottheimer"},
    {"id": "dan_crenshaw", "name": "Dan Crenshaw", "rx": r"dan\s+crenshaw"},
    {"id": "tommy_tuberville", "name": "Tommy Tuberville", "rx": r"tommy\s+tuberville"},
]

POLITICIANS_INDIA: list[dict[str, Any]] = [
    {"id": "mp_stock", "name": "MP stock disclosure", "rx": r"mp\s+(buy|purchase|invest)|member\s+of\s+parliament.*(stock|share)", "require_buy": False},
    {"id": "lok_sabha", "name": "Lok Sabha disclosure", "rx": r"lok\s+sabha.*(stock|share|invest)|rajya\s+sabha.*(stock|share)", "require_buy": False},
    {"id": "politician_india", "name": "Politician India", "rx": r"politician.*(buy|stake|share)|minister.*(buy|stake|shareholding)", "require_buy": False},
]

# US / global funds explicitly buying Indian names
FOREIGN_INDIA: list[dict[str, Any]] = [
    {"id": "fii_buy_india", "name": "FII buying India", "rx": r"fii.*(buy|inflow|net\s+buy)|foreign\s+institutional.*(buy|inflow)", "require_buy": False},
    {"id": "us_fund_india_stake", "name": "US fund India stake", "rx": r"(blackrock|vanguard|berkshire|sovereign|abu\s+dhabi|singapore\s+gic|temasek).*(india|indian|nse|bse|\.ns|reliance|tata|infosys|hdfc)", "require_buy": False},
    {"id": "adr_india_buy", "name": "ADR / India exposure buy", "rx": r"(increases|raises|builds).*(stake|holding|position).*(india|indian\s+stock|adr)", "require_buy": False},
]


@dataclass
class SmartMoneyMatch:
    entity_id: str
    display_name: str
    kind: str  # india_legend | us_legend | politician_us | politician_india | foreign_india
    tier: str  # S+ | S | A
    headline: str = ""

    def alert_text(self) -> str:
        prefix = {
            "india_legend": "🇮🇳 LEGEND BUY",
            "us_legend": "🇺🇸 WHALE BUY",
            "politician_us": "🏛️ POLITICIAN BUY",
            "politician_india": "🏛️ POLITICIAN BUY",
            "foreign_india": "🌐 FOREIGN BUY",
        }.get(self.kind, "💰 SMART MONEY")
        return f"{prefix}: {self.display_name}"


@dataclass
class SmartMoneyIntel:
    matches: list[SmartMoneyMatch] = field(default_factory=list)
    india_legend: bool = False
    us_legend: bool = False
    politician_us: bool = False
    politician_india: bool = False
    foreign_india: bool = False
    primary_alert: str | None = None
    names: list[str] = field(default_factory=list)

    def to_metrics(self) -> dict[str, Any]:
        return {
            "hits": [
                {
                    "id": m.entity_id,
                    "name": m.display_name,
                    "kind": m.kind,
                    "tier": m.tier,
                    "headline": m.headline[:120],
                }
                for m in self.matches[:8]
            ],
            "names": self.names[:6],
            "primary_alert": self.primary_alert,
            "india_legend": self.india_legend,
            "us_legend": self.us_legend,
            "politician_us": self.politician_us,
            "politician_india": self.politician_india,
            "foreign_india": self.foreign_india,
        }


def _compile_registry(entries: list[dict], default_kind: str, default_tier: str) -> list[dict]:
    out = []
    for e in entries:
        out.append(
            {
                **e,
                "kind": e.get("kind", default_kind),
                "tier": e.get("tier", default_tier),
                "pattern": re.compile(e["rx"], re.I),
            }
        )
    return out


def _load_extra_registry() -> list[dict]:
    """data/smart_money_extra.txt — lines: kind|regex|Display Name"""
    if not _EXTRA_FILE.exists():
        return []
    extras: list[dict] = []
    for line in _EXTRA_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        kind, rx, name = (p.strip() for p in parts)
        eid = re.sub(r"[^a-z0-9]+", "_", name.lower())[:40] or "extra"
        extras.append(
            {"id": f"extra_{eid}", "name": name, "rx": rx, "kind": kind, "tier": "S+"}
        )
    return extras


REGISTRY: list[dict] = (
    _compile_registry(INDIA_LEGENDS, "india_legend", "S+")
    + _compile_registry(US_LEGENDS, "us_legend", "S+")
    + _compile_registry(POLITICIANS_US, "politician_us", "S+")
    + _compile_registry(POLITICIANS_INDIA, "politician_india", "S+")
    + _compile_registry(FOREIGN_INDIA, "foreign_india", "S")
    + _compile_registry(_load_extra_registry(), "india_legend", "S+")  # kind per line in file
)


def _title_matches(entry: dict, title: str) -> bool:
    if not entry["pattern"].search(title):
        return False
    if entry.get("require_buy", True) and not BUY_CONTEXT.search(title):
        return False
    return True


def analyze_smart_money(titles: list[str], *, market: str = "both") -> SmartMoneyIntel:
    """Scan headlines for named smart-money buy activity."""
    intel = SmartMoneyIntel()
    if not titles:
        return intel

    seen: set[str] = set()
    for title in titles[-40:]:
        t = title.strip()
        if not t:
            continue
        for entry in REGISTRY:
            eid = entry["id"]
            if eid in seen:
                continue
            kind = entry["kind"]
            if market == "us" and kind in ("india_legend", "politician_india", "foreign_india"):
                continue
            if market == "india" and kind in ("politician_us",):
                continue
            if not _title_matches(entry, t):
                continue
            seen.add(eid)
            m = SmartMoneyMatch(
                entity_id=eid,
                display_name=entry["name"],
                kind=kind,
                tier=entry["tier"],
                headline=t,
            )
            intel.matches.append(m)
            intel.names.append(entry["name"])
            if kind == "india_legend":
                intel.india_legend = True
            elif kind == "us_legend":
                intel.us_legend = True
            elif kind == "politician_us":
                intel.politician_us = True
            elif kind == "politician_india":
                intel.politician_india = True
            elif kind == "foreign_india":
                intel.foreign_india = True

    # Best alert: S+ legends first, then politicians
    priority = {"S+": 0, "S": 1, "A": 2}
    kind_priority = {
        "india_legend": 0,
        "us_legend": 1,
        "politician_us": 2,
        "politician_india": 2,
        "foreign_india": 3,
    }
    if intel.matches:
        best = sorted(
            intel.matches,
            key=lambda m: (priority.get(m.tier, 9), kind_priority.get(m.kind, 9)),
        )[0]
        intel.primary_alert = best.alert_text()

    return intel


def registry_for_api() -> list[dict[str, str]]:
    """Expose tracked names for /api/factors documentation."""
    return [
        {"id": e["id"], "name": e["name"], "kind": e["kind"], "market": "india" if "india" in e["kind"] else "us" if e["kind"] == "us_legend" else "both"}
        for e in REGISTRY
    ]