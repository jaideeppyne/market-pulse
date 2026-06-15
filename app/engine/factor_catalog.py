from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorDef:
    id: str
    category: str
    name: str
    description: str
    market: str = "both"  # both | us | india


# Master checklist — every row is one factor you can click to read
FACTOR_CATALOG: list[FactorDef] = [
    # Fundamental & cash (12)
    FactorDef("fcf_positive", "fundamental", "Positive FCF", "Free cash flow > 0", "both"),
    FactorDef("fcf_yield_high", "fundamental", "FCF yield", "FCF / market cap ≥ 3%", "both"),
    FactorDef("operating_cf_positive", "fundamental", "Operating cash flow", "Operating CF > 0", "both"),
    FactorDef("operating_margin", "fundamental", "Operating margin", "Operating margin > 12%", "both"),
    FactorDef("net_margin_strong", "fundamental", "Net margin", "Net profit margin > 10%", "both"),
    FactorDef("gross_margin_strong", "fundamental", "Gross margin", "Gross margin > 35%", "both"),
    FactorDef("revenue_growth", "fundamental", "Revenue growth", "YoY revenue growth > 10%", "both"),
    FactorDef("earnings_growth", "fundamental", "Earnings growth", "YoY earnings growth > 10%", "both"),
    FactorDef("roe_strong", "fundamental", "ROE", "Return on equity > 15%", "both"),
    FactorDef("roa_positive", "fundamental", "ROA", "Return on assets > 5%", "both"),
    FactorDef("cash_per_share", "fundamental", "Cash / share", "Total cash > total debt (net cash bias)", "both"),
    FactorDef("interest_coverage", "fundamental", "Interest coverage", "EBITDA covers interest (proxy)", "both"),
    # Valuation (8)
    FactorDef("pe_sector_ok", "valuation", "P/E (sector)", "Trailing P/E inside sector band", "both"),
    FactorDef("forward_pe_ok", "valuation", "Forward P/E", "Forward P/E reasonable vs sector", "both"),
    FactorDef("pb_sector_ok", "valuation", "P/B (sector)", "P/B in range — key for banks/insurance", "both"),
    FactorDef("pb_reasonable", "valuation", "P/B reasonable", "Price to book not extreme", "both"),
    FactorDef("peg_attractive", "valuation", "PEG ratio", "PEG between 0 and 1.5", "both"),
    FactorDef("ev_revenue_ok", "valuation", "EV / Revenue", "Enterprise value to revenue < 5", "both"),
    FactorDef("price_below_target", "valuation", "Analyst upside", "Price below consensus target (upside)", "both"),
    FactorDef("analyst_buy_bias", "valuation", "Analyst rating", "Buy / strong buy consensus", "both"),
    # Financial health (5)
    FactorDef("debt_manageable", "health", "Debt / equity", "Debt to equity < 80", "both"),
    FactorDef("liquidity_current_ratio", "health", "Current ratio", "Current assets / liabilities > 1.2", "both"),
    FactorDef("liquidity_quick_ratio", "health", "Quick ratio", "Quick ratio > 1.0", "both"),
    FactorDef("payout_sustainable", "health", "Payout ratio", "Dividend payout < 70%", "both"),
    FactorDef("beta_moderate", "health", "Beta", "Beta 0.6–1.8 (not extreme)", "both"),
    # Ownership (5)
    FactorDef("institutional_holding", "ownership", "Institutional %", "US: institutions hold > 45%", "us"),
    FactorDef("insider_holding", "ownership", "Insider / promoter %", "Insider or promoter stake > 25%", "both"),
    FactorDef("low_short_interest", "ownership", "Low short interest", "US: short float < 8%", "us"),
    FactorDef("high_short", "risk", "High short interest", "US: short float > 20% — caution", "us"),
    FactorDef("float_liquidity", "ownership", "Share liquidity", "Avg daily $ volume adequate", "both"),
    # Income & calendar (6)
    FactorDef("dividend_yield", "income", "Dividend yield", "Yield > 1.5%", "both"),
    FactorDef("dividend_upcoming", "calendar", "Ex-dividend soon", "Ex-dividend within 14 days", "both"),
    FactorDef("dividend_news", "income", "Dividend news", "Dividend announced in headlines", "both"),
    FactorDef("earnings_today", "calendar", "Earnings today", "Results today", "both"),
    FactorDef("earnings_3d", "calendar", "Earnings ≤3 days", "Results within 3 days", "both"),
    FactorDef("earnings_7d", "calendar", "Earnings ≤7 days", "Results within 7 days", "both"),
    # Technical (12)
    FactorDef("rsi_bull_zone", "technical", "RSI bull zone", "RSI 48–68", "both"),
    FactorDef("rsi_oversold_bounce", "technical", "RSI oversold bounce", "RSI < 32 with green day", "both"),
    FactorDef("rsi_overbought", "risk", "RSI overbought", "RSI > 78 — caution", "both"),
    FactorDef("near_52w_high", "technical", "Near 52w high", "Price ≥ 92% of 52-week high", "both"),
    FactorDef("breakout_52w", "technical", "52w breakout", "New 52-week high today", "both"),
    FactorDef("near_52w_low", "technical", "Near 52w low", "Within 15% of 52-week low", "both"),
    FactorDef("cup_handle", "technical", "Cup & handle", "Multi-month base + handle", "both"),
    FactorDef("macd_bullish", "technical", "MACD bullish", "MACD above signal / cross up", "both"),
    FactorDef("ma_bull_stack", "technical", "MA bull stack", "Price above rising 20/50/200 MAs", "both"),
    FactorDef("above_50dma", "technical", "Above 50-day MA", "Price above 50-day average", "both"),
    FactorDef("golden_cross_zone", "technical", "Golden cross zone", "50 MA crossing above 200 MA", "both"),
    # New simple DMA/EMA + support/resistance (proven user-friendly signals)
    FactorDef("near_50dma", "technical", "Near 50 DMA", "Price at/near 50-day moving average (classic support)", "both"),
    FactorDef("near_200dma", "technical", "Near 200 DMA", "Price at/near major 200-day MA (strong support/resistance)", "both"),
    FactorDef("near_ema20", "technical", "Near 20 EMA", "Price near fast 20-period EMA", "both"),
    FactorDef("dma_ema_bull_support", "technical", "DMA/EMA bullish support", "Price holding support above key DMAs or EMA alignment", "both"),
    FactorDef("near_dma_support", "entry", "Support at DMA/EMA", "Price taking support near 50/200 DMA or 20 EMA - simple buy zone", "both"),
    # Volume & momentum (10)
    FactorDef("rvol_surge", "volume", "Volume surge", "Relative volume ≥ 2.5×", "both"),
    FactorDef("rvol_above_avg", "volume", "Above-avg volume", "Relative volume ≥ 1.6×", "both"),
    FactorDef("volume_trend_up", "volume", "Volume trend up", "10-day volume rising", "both"),
    FactorDef("accumulation_day", "volume", "Accumulation day", "Up day + high volume", "both"),
    FactorDef("momentum_5d", "momentum", "5-day momentum", "5-day return ≥ 8%", "both"),
    FactorDef("momentum_20d", "momentum", "20-day momentum", "20-day return ≥ 15%", "both"),
    FactorDef("intraday_move", "momentum", "Big day move", "Daily move ≥ 4%", "both"),
    FactorDef("post_market_gap", "momentum", "Post-market gap", "After-hours move ≥ 2.5%", "both"),
    FactorDef("pre_market_gap", "momentum", "Pre-market gap", "Pre-market move ≥ 2%", "both"),
    FactorDef("distribution_day", "risk", "Distribution day", "Down day on heavy volume", "both"),
    # News & catalysts (12)
    FactorDef("news_burst", "news", "News burst", "3+ headlines in window", "both"),
    FactorDef("in_news", "news", "In the news", "1+ matched headline", "both"),
    FactorDef("news_policy_gov", "catalyst", "Govt / PLI / policy", "Government or PLI tailwind in news", "both"),
    FactorDef("news_order_contract", "catalyst", "Orders / contracts", "Order book, tender, contract news", "both"),
    FactorDef("news_merger_acquisition", "catalyst", "M&A talk", "Merger, acquisition, takeover headlines", "both"),
    FactorDef("news_famous_investor", "catalyst", "Famous investor", "Buffett, ARK, top India investors", "both"),
    FactorDef("smart_money_india_legend", "catalyst", "India legend buy", "Kela, Kacholia, Kedia, etc. + buy headline", "india"),
    FactorDef("smart_money_us_legend", "catalyst", "US whale buy", "Buffett, Ackman, ARK, etc. + buy headline", "us"),
    FactorDef("smart_money_politician", "catalyst", "Politician buy", "Named politician / STOCK Act / MP disclosure", "both"),
    FactorDef("smart_money_foreign_india", "catalyst", "Foreign buy (India)", "FII / US fund raising India stake", "india"),
    FactorDef("news_politician", "catalyst", "Politician activity", "Politician trading / disclosure news", "us"),
    FactorDef("news_insider_buy", "catalyst", "Insider / promoter buy", "Insider buying in news", "both"),
    FactorDef("news_analyst_positive", "catalyst", "Analyst upgrade", "Upgrade or PT raise", "both"),
    FactorDef("news_earnings_positive", "catalyst", "Positive earnings news", "Beat, record profit headlines", "both"),
    FactorDef("news_buyback", "catalyst", "Buyback news", "Share buyback announced", "both"),
    FactorDef("news_fda_approval", "catalyst", "FDA / approval", "Regulatory approval (esp. pharma)", "us"),
    FactorDef("news_sector_tailwind", "catalyst", "Sector tailwind", "Sector rally / capex news", "both"),
    FactorDef("news_fii_flow", "catalyst", "FII / flows (India)", "FII, DII, flow mention in news", "india"),
    FactorDef("event_ceo_buy", "catalyst", "CEO open-market buy", "CEO / MD personally bought company shares", "both"),
    FactorDef("event_cfo_buy", "catalyst", "CFO open-market buy", "CFO personally bought company shares", "both"),
    FactorDef("event_director_buy", "catalyst", "Director open-market buy", "Director bought company shares", "both"),
    FactorDef("event_insider_buy", "catalyst", "Official insider buy", "SEC Form 4 or structured insider/promoter buy event", "both"),
    FactorDef("event_promoter_buy", "catalyst", "Promoter / management buy", "India promoter/management buying or stake increase", "india"),
    FactorDef("event_bulk_block_deal", "catalyst", "Bulk / block deal event", "Structured bulk/block deal event", "india"),
    # Sector-specific (5)
    FactorDef("bank_roe", "sector", "Bank ROE", "Bank: ROE > 12%", "both"),
    FactorDef("tech_growth", "sector", "Tech growth", "Tech: revenue growth > 15%", "both"),
    FactorDef("utility_yield", "sector", "Utility yield", "Utility: yield > 3%", "both"),
    FactorDef("india_defense_policy", "sector", "India defense / PSU", "Defense PSU + policy news", "india"),
    FactorDef("energy_fcf", "sector", "Energy FCF", "Energy: positive FCF", "both"),
    # Entry / next-buy (not already extended)
    FactorDef("room_to_run", "entry", "Room to run", "Price 68–88% of 52w range — not chasing the top", "both"),
    FactorDef("deep_value_zone", "entry", "Deep value zone", "Bottom 30% of 52w range with improving tone", "both"),
    FactorDef("rsi_turning_up", "entry", "RSI turning up", "RSI rising from oversold — early momentum", "both"),
    FactorDef("pullback_50dma", "entry", "Pullback to 50 DMA", "Price hugging 50-day MA after pullback", "both"),
    FactorDef("base_compression", "entry", "Tight base", "20-day range compression (coiling)", "both"),
    FactorDef("higher_lows", "entry", "Higher lows", "Series of rising swing lows", "both"),
    FactorDef("pre_breakout_vol", "entry", "Pre-breakout volume", "RVOL rising but price not at 52w high", "both"),
    FactorDef("rs_turn_positive", "entry", "RS turn", "5d green while 20d still muted — early leg", "both"),
    FactorDef("reclaim_20dma", "entry", "Reclaim 20 DMA", "Price crossed back above 20-day MA", "both"),
    FactorDef("cup_forming", "entry", "Cup forming", "Cup/handle base building, not extended", "both"),
    FactorDef("earnings_pre_catalyst", "entry", "Pre-earnings setup", "Earnings in 5–14 days + solid base", "both"),
    FactorDef("short_squeeze_setup", "entry", "Short squeeze setup", "High short + price/volume turning (US)", "us"),
    FactorDef("pe_below_sector", "entry", "P/E discount", "P/E below sector midpoint", "both"),
    FactorDef("below_analyst_target", "entry", "Below street target", "20%+ upside to consensus target", "both"),
    # More news / crawl catalysts
    FactorDef("news_turnaround", "catalyst", "Turnaround news", "Restructuring / recovery headlines", "both"),
    FactorDef("news_new_ceo", "catalyst", "New CEO / MD", "Leadership change — re-rating potential", "both"),
    FactorDef("news_expansion", "catalyst", "Expansion / capex", "New plants, capacity, capex plans", "both"),
    FactorDef("news_partnership", "catalyst", "Partnership / JV", "Alliance or joint venture news", "both"),
    FactorDef("news_patent", "catalyst", "Patent / IP", "IP or breakthrough mention", "both"),
    FactorDef("news_guidance_raise", "catalyst", "Guidance raised", "Outlook or guidance upgrade", "both"),
    FactorDef("news_init_coverage", "catalyst", "New coverage", "Initiation of analyst coverage", "both"),
    FactorDef("news_stake_increase", "catalyst", "Stake increase", "Promoter/parent increasing holding", "both"),
    FactorDef("news_bulk_deal", "catalyst", "Bulk / block deal", "India block/bulk deal activity", "india"),
    FactorDef("news_qip", "catalyst", "QIP / fundraise", "Qualified / preferential raise (watch dilution)", "india"),
    FactorDef("news_ai_theme", "catalyst", "AI theme", "AI / data-center narrative in news", "both"),
    FactorDef("news_semiconductor", "catalyst", "Semiconductor theme", "Chip / fab narrative", "both"),
    FactorDef("news_export_order", "catalyst", "Export demand", "Export growth or overseas orders", "both"),
    FactorDef("news_short_squeeze", "catalyst", "Short squeeze talk", "High short + squeeze headlines", "us"),
    FactorDef("news_rate_cut", "catalyst", "Rate-cut beneficiary", "Easing / dovish policy tailwind", "both"),
    FactorDef("news_bank_npa", "catalyst", "Bank NPA improve", "Asset quality / NPA improvement", "india"),
    FactorDef("news_lawsuit_win", "catalyst", "Legal win", "Settlement or legal overhang cleared", "both"),
    FactorDef("news_tariff_relief", "catalyst", "Tariff relief", "Trade / duty relief headlines", "both"),
    # Extension / chase risks (penalize buy score)
    FactorDef("extended_run", "risk", "Extended run", "20d +25% and near 52w high — late chase", "both"),
    FactorDef("chase_risk", "risk", "Chase risk", "Near high + hot 5d momentum", "both"),
    FactorDef("parabolic_move", "risk", "Parabolic 5d", "5-day spike > 15% — blow-off risk", "both"),
    FactorDef("already_at_high", "risk", "At 52w high", "Price ≥ 98% of 52w — limited upside left", "both"),
]

FACTORS_TOTAL = len(FACTOR_CATALOG)

CATEGORY_ORDER = [
    "entry",
    "fundamental",
    "valuation",
    "health",
    "ownership",
    "income",
    "calendar",
    "technical",
    "volume",
    "momentum",
    "news",
    "catalyst",
    "sector",
    "risk",
]

ENTRY_FACTOR_IDS = frozenset(
    f.id for f in FACTOR_CATALOG if f.category == "entry"
) | {"near_dma_support", "dma_ema_bull_support"}  # simple tech support signals get entry boost too
RISK_EXTENSION_IDS = frozenset(
    {"extended_run", "chase_risk", "parabolic_move", "already_at_high", "rsi_overbought"}
)


def catalog_for_api() -> list[dict]:
    return [
        {
            "id": f.id,
            "category": f.category,
            "name": f.name,
            "description": f.description,
            "market": f.market,
        }
        for f in FACTOR_CATALOG
    ]


def _market_applies(factor_market: str, stock_market: str) -> bool:
    if factor_market == "both":
        return True
    return factor_market == stock_market


def build_factor_breakdown(hits: list, stock_market: str) -> list[dict]:
    """Full checklist: pass / fail / risk / na for every catalog factor."""
    by_id = {h.id: h for h in hits}
    out: list[dict] = []
    for f in FACTOR_CATALOG:
        if not _market_applies(f.market, stock_market):
            out.append(
                {
                    "id": f.id,
                    "category": f.category,
                    "name": f.name,
                    "description": f.description,
                    "status": "na",
                    "label": None,
                    "points": 0,
                }
            )
            continue
        hit = by_id.get(f.id)
        if hit is None:
            out.append(
                {
                    "id": f.id,
                    "category": f.category,
                    "name": f.name,
                    "description": f.description,
                    "status": "fail",
                    "label": None,
                    "points": 0,
                }
            )
        elif hit.points > 0:
            out.append(
                {
                    "id": f.id,
                    "category": f.category,
                    "name": f.name,
                    "description": f.description,
                    "status": "pass",
                    "label": hit.label,
                    "points": hit.points,
                }
            )
        else:
            out.append(
                {
                    "id": f.id,
                    "category": f.category,
                    "name": f.name,
                    "description": f.description,
                    "status": "risk",
                    "label": hit.label,
                    "points": 0,
                }
            )
    return out


def count_applicable(breakdown: list[dict]) -> tuple[int, int]:
    """Returns (passed, applicable_total) excluding na."""
    applicable = [x for x in breakdown if x["status"] != "na"]
    passed = sum(1 for x in applicable if x["status"] == "pass")
    return passed, len(applicable)
