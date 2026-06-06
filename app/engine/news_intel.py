from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class NewsIntel:
    titles: list[str] = field(default_factory=list)
    policy_gov: bool = False
    order_contract: bool = False
    merger_acquisition: bool = False
    famous_investor: bool = False
    politician: bool = False
    insider_buy: bool = False
    analyst_positive: bool = False
    earnings_positive: bool = False
    dividend_news: bool = False
    sector_tailwind: bool = False
    buyback: bool = False
    fda_approval: bool = False
    fii_flow: bool = False
    # Expanded crawl signals (early / catalyst)
    turnaround: bool = False
    new_ceo: bool = False
    expansion_capex: bool = False
    partnership: bool = False
    patent_ip: bool = False
    guidance_raise: bool = False
    init_coverage: bool = False
    stake_increase: bool = False
    bulk_block_deal: bool = False
    qip_fundraise: bool = False
    lawsuit_win: bool = False
    rate_cut_benefit: bool = False
    commodity_tailwind: bool = False
    ai_theme: bool = False
    semiconductor_theme: bool = False
    export_order: bool = False
    capacity_expansion: bool = False
    short_squeeze_talk: bool = False
    tariff_relief: bool = False
    banking_npa_improve: bool = False

    def hit_count(self) -> int:
        return sum(
            1
            for k, v in self.__dict__.items()
            if k != "titles" and v is True
        )


PATTERNS = {
    "policy_gov": re.compile(
        r"pli|government|govt|federal|modi|budget|chips act|make in india|"
        r"subsidy|indigenization|defence policy|defense policy|psu|tariff relief",
        re.I,
    ),
    "order_contract": re.compile(
        r"order book|contract award|tender|billion.?deal|multi.?year contract|"
        r"defence order|defense order|procurement|backlog|wins order",
        re.I,
    ),
    "merger_acquisition": re.compile(
        r"merger|acquisition|acquires|takeover|buyout|stake sale|strategic investment|"
        r"amalgamation|demerger",
        re.I,
    ),
    "famous_investor": re.compile(
        r"buffett|berkshire|ark invest|cathie wood|dalio|bridgewater|"
        r"icahn|ackman|pershing|baupost|sequoia|softbank|masayoshi|"
        r"raakesh jhunjhunwala|rakesh jhunjhunwala|dolly khanna|ashish kacholia|"
        r"madhusudan kela|mk kela|vijay kedia|radhakishan damani|porinju|"
        r"shankar sharma|nemish shah|sunil singhania|kenneth andrade|"
        r"tepper|druckenmiller|loeb|klarman|tiger global|coatue",
        re.I,
    ),
    "politician": re.compile(
        r"senator|congressman|congresswoman|pelosi|politician|mp buys|"
        r"lok sabha|rajya sabha|stock act|capitol trades|"
        r"disclosure.*stock|congress.*trading|minister.*shareholding",
        re.I,
    ),
    "insider_buy": re.compile(
        r"insider buy|insider purchase|form 4|director buy|promoter buy|"
        r"promoter stake|increases stake|open market purchase",
        re.I,
    ),
    "analyst_positive": re.compile(
        r"upgrade|price target raised|outperform|overweight|buy rating|"
        r"raises target|bullish on|initiates coverage.*buy",
        re.I,
    ),
    "earnings_positive": re.compile(
        r"beats estimates|earnings beat|profit surge|record profit|"
        r"strong quarter|tops expectations",
        re.I,
    ),
    "dividend_news": re.compile(
        r"dividend|interim dividend|special dividend|ex.?dividend|payout",
        re.I,
    ),
    "sector_tailwind": re.compile(
        r"tailwind|sector rally|policy boost|sector upgrade|demand boom|"
        r"sector rotation|outperform sector",
        re.I,
    ),
    "buyback": re.compile(
        r"buyback|share repurchase|repurchase program|buy.?back",
        re.I,
    ),
    "fda_approval": re.compile(
        r"fda approval|fda clears|phase 3 success|drug approved|"
        r"regulatory approval|breakthrough therapy",
        re.I,
    ),
    "fii_flow": re.compile(
        r"fii|dii|foreign institutional|domestic institutional|"
        r"fiis buy|fiis net|fund flow india|nifty inflow",
        re.I,
    ),
    "turnaround": re.compile(
        r"turnaround|restructuring|debt reduction|loss narrows|returns to profit|"
        r"recovery plan|margin recovery",
        re.I,
    ),
    "new_ceo": re.compile(
        r"new ceo|new chief executive|appoints ceo|leadership change|"
        r"managing director appointed",
        re.I,
    ),
    "expansion_capex": re.compile(
        r"capex|capital expenditure|new plant|greenfield|brownfield|"
        r"facility expansion|manufacturing hub",
        re.I,
    ),
    "partnership": re.compile(
        r"partnership|strategic alliance|joint venture|collaboration with|"
        r"licensing deal|supply agreement",
        re.I,
    ),
    "patent_ip": re.compile(
        r"patent|intellectual property|ip win|proprietary tech|breakthrough",
        re.I,
    ),
    "guidance_raise": re.compile(
        r"guidance raise|raises guidance|outlook raised|forecast upgrade|"
        r"raises full.?year",
        re.I,
    ),
    "init_coverage": re.compile(
        r"initiates coverage|initiation of coverage|starts coverage|"
        r"first coverage",
        re.I,
    ),
    "stake_increase": re.compile(
        r"stake increase|raises holding|accumulates shares|"
        r"parent ups stake|promoter increases|promoter buy|promoter stake rise",
        re.I,
    ),
    "bulk_block_deal": re.compile(
        r"bulk deal|block deal|large trade nse|bse bulk|"
        r"institutional block|bulk purchase|block purchase",
        re.I,
    ),
    "qip_fundraise": re.compile(
        r"qip|qualified institutional|fund raise|fpo|rights issue|"
        r"preferential allotment",
        re.I,
    ),
    "lawsuit_win": re.compile(
        r"lawsuit settled|court win|legal victory|settlement reached|"
        r"cleared of charges",
        re.I,
    ),
    "rate_cut_benefit": re.compile(
        r"rate cut|fed pivot|dovish|lower interest rates|"
        r"rbi cuts repo|monetary easing",
        re.I,
    ),
    "commodity_tailwind": re.compile(
        r"oil price drop|metal prices rally|commodity boom|"
        r"input cost relief|freight costs fall",
        re.I,
    ),
    "ai_theme": re.compile(
        r"\bai\b|artificial intelligence|machine learning|llm|"
        r"generative ai|data center build",
        re.I,
    ),
    "semiconductor_theme": re.compile(
        r"semiconductor|chip maker|foundry|wafer|fab plant|"
        r"advanced packaging",
        re.I,
    ),
    "export_order": re.compile(
        r"export order|overseas demand|export growth|"
        r"international expansion",
        re.I,
    ),
    "capacity_expansion": re.compile(
        r"capacity expansion|doubling capacity|ramp up production|"
        r"new production line",
        re.I,
    ),
    "short_squeeze_talk": re.compile(
        r"short squeeze|high short interest|days to cover|"
        r"short sellers burned",
        re.I,
    ),
    "tariff_relief": re.compile(
        r"tariff relief|trade deal|import duty cut|"
        r"anti.?dumping withdrawn",
        re.I,
    ),
    "banking_npa_improve": re.compile(
        r"npa ratio falls|asset quality improves|gnpa|"
        r"provision coverage|net interest margin expands",
        re.I,
    ),
}


def analyze_news_titles(titles: list[str]) -> NewsIntel:
    intel = NewsIntel(titles=titles[-30:])
    blob = " ".join(titles).lower()
    if not blob.strip():
        return intel
    for attr, rx in PATTERNS.items():
        if rx.search(blob):
            setattr(intel, attr, True)
    return intel