from __future__ import annotations

import pandas as pd

from app.engine.context import ScanContext
from app.engine.types import FactorHit
from app.engine.factor_catalog import (  # noqa: F401 — re-export
    ENTRY_FACTOR_IDS,
    FACTORS_TOTAL,
    build_factor_breakdown,
    count_applicable,
)
from app.engine.factor_weights import factor_weight, tier_label, weighted_points
from app.engine.scoring import _compute_scores
from app.engine.indicators import (
    cup_handle_score,
    dma,
    ema,
    higher_lows,
    ma_alignment,
    macd_signal,
    ma_support_resistance,
    near_ma_pullback,
    pct_52w_range,
    range_compression,
    rsi,
    rsi_turning_up,
    volume_trend,
)

# 100+ factors · buy_score ranks "next buy" (penalizes already-extended names)


def _hits(ctx: ScanContext) -> list[FactorHit]:
    h: list[FactorHit] = []
    i = ctx.info
    vt = ctx.val_thresholds
    close = ctx.hist["Close"]
    volume = ctx.hist["Volume"]

    def add(fid: str, cat: str, label: str, pts: float, alert: str | None = None):
        h.append(FactorHit(fid, cat, label, pts, alert))

    # --- FUNDAMENTALS (profits & cash) ---
    fcf = i.get("freeCashflow")
    mcap = i.get("marketCap")
    if fcf and fcf > 0:
        add("fcf_positive", "fundamental", "Positive free cash flow", 2.5)
    if fcf and mcap and mcap > 0 and (fcf / mcap) >= 0.03:
        add("fcf_yield_high", "fundamental", f"FCF yield {(fcf/mcap)*100:.1f}%", 2.0)
    op_cf = i.get("operatingCashflow")
    if op_cf and op_cf > 0:
        add("operating_cf_positive", "fundamental", "Positive operating cash flow", 2.0)
    if i.get("profitMargins") and i["profitMargins"] > 0.10:
        add("net_margin_strong", "fundamental", f"Net margin {i['profitMargins']*100:.0f}%", 2.0)
    if i.get("grossMargins") and i["grossMargins"] > 0.35:
        add("gross_margin_strong", "fundamental", "Strong gross margin", 1.5)
    if i.get("revenueGrowth") and i["revenueGrowth"] > 0.10:
        add("revenue_growth", "fundamental", f"Revenue growth {i['revenueGrowth']*100:.0f}%", 2.0)
    if i.get("earningsGrowth") and i["earningsGrowth"] > 0.10:
        add("earnings_growth", "fundamental", f"Earnings growth {i['earningsGrowth']*100:.0f}%", 2.0)
    if i.get("returnOnEquity") and i["returnOnEquity"] > 0.15:
        add("roe_strong", "fundamental", f"ROE {i['returnOnEquity']*100:.0f}%", 2.0)
    if i.get("returnOnAssets") and i["returnOnAssets"] > 0.05:
        add("roa_positive", "fundamental", f"ROA {i['returnOnAssets']*100:.1f}%", 1.5)
    if i.get("operatingMargins") and i["operatingMargins"] > 0.12:
        add("operating_margin", "fundamental", f"Op margin {i['operatingMargins']*100:.0f}%", 1.5)
    cash = i.get("totalCash")
    debt = i.get("totalDebt")
    if cash and debt is not None and cash > debt:
        add("cash_per_share", "fundamental", "Net cash position", 1.5)
    ebitda = i.get("ebitda")
    interest = i.get("interestExpense")
    if ebitda and interest and interest != 0 and abs(interest) > 0:
        cov = ebitda / abs(interest)
        if cov > 3:
            add("interest_coverage", "fundamental", f"Interest cover {cov:.1f}x", 1.5)

    # --- VALUATION (PE/PB sector-aware) ---
    pe = i.get("trailingPE")
    pb = i.get("priceToBook")
    peg = i.get("pegRatio")
    fpe = i.get("forwardPE")
    if pe and vt["pe_low"] < pe < vt["pe_high"]:
        add("pe_sector_ok", "valuation", f"P/E {pe:.1f} (sector band)", 2.0)
    if fpe and vt["pe_low"] < fpe < vt["pe_high"] * 1.15:
        add("forward_pe_ok", "valuation", f"Forward P/E {fpe:.1f}", 1.5)
    if vt.get("prefer_pb_over_pe") and pb and vt["pb_low"] < pb < vt["pb_high"]:
        add("pb_sector_ok", "valuation", f"P/B {pb:.2f} (key for {ctx.bucket})", 2.5)
    elif not vt.get("prefer_pb_over_pe") and pb and 0 < pb < vt.get("pb_high", 6):
        add("pb_reasonable", "valuation", f"P/B {pb:.2f}", 1.5)
    if peg and 0 < peg < 1.5:
        add("peg_attractive", "valuation", f"PEG {peg:.2f}", 2.0)
    ev_rev = i.get("enterpriseToRevenue")
    if ev_rev and 0 < ev_rev < 5:
        add("ev_revenue_ok", "valuation", "EV/Revenue reasonable", 1.0)
    target = i.get("targetMeanPrice")
    if target and ctx.price and ctx.price < target * 0.98:
        upside = (target / ctx.price - 1) * 100
        add("price_below_target", "valuation", f"Upside to target {upside:.0f}%", 2.0)
    rec = i.get("recommendationMean")
    if rec is not None and rec <= 2.3:
        add("analyst_buy_bias", "valuation", "Analyst buy bias", 1.5)

    # --- FINANCIAL HEALTH ---
    de = i.get("debtToEquity")
    if de is not None and de < 80:
        add("debt_manageable", "health", f"Debt/Equity {de:.0f}", 1.5)
    cr = i.get("currentRatio")
    if cr and cr > 1.2:
        add("liquidity_current_ratio", "health", f"Current ratio {cr:.2f}", 1.5)
    qr = i.get("quickRatio")
    if qr and qr > 1.0:
        add("liquidity_quick_ratio", "health", f"Quick ratio {qr:.2f}", 1.0)
    payout = i.get("payoutRatio")
    if payout is not None and 0 < payout < 0.70:
        add("payout_sustainable", "health", f"Payout {payout*100:.0f}%", 1.0)
    beta = i.get("beta")
    if beta is not None and 0.6 <= beta <= 1.8:
        add("beta_moderate", "health", f"Beta {beta:.2f}", 1.0)

    # --- OWNERSHIP (US: institutional; India: promoter proxy via insiders) ---
    inst = i.get("heldPercentInstitutions")
    if inst and inst > 0.45 and ctx.market == "us":
        add("institutional_holding", "ownership", f"Institutional {inst*100:.0f}%", 2.0)
    insider = i.get("heldPercentInsiders")
    if insider and insider > 0.25:
        label = "Promoter/insider holding" if ctx.market == "india" else "Insider holding"
        add("insider_holding", "ownership", f"{label} {insider*100:.0f}%", 2.0)
    short = i.get("shortPercentOfFloat")
    if short is not None and short < 0.08 and ctx.market == "us":
        add("low_short_interest", "ownership", f"Short {short*100:.1f}% float", 1.5)
    elif short and short > 0.20:
        h.append(FactorHit("high_short", "risk", f"High short {short*100:.0f}%", 0, "HIGH SHORT"))
    avg_vol = i.get("averageVolume") or i.get("averageVolume10days")
    dollar_vol = (avg_vol or 0) * ctx.price
    min_liq = 3_000_000 if ctx.market == "us" else 50_000_000
    if dollar_vol >= min_liq:
        add("float_liquidity", "ownership", "Adequate trading liquidity", 1.0)

    # --- DIVIDEND & CALENDAR ---
    dy = i.get("dividendYield")
    if dy and dy > 0.015:
        add("dividend_yield", "income", f"Div yield {dy*100:.2f}%", 1.5)
    if ctx.dividend_days is not None and ctx.dividend_days <= 14:
        add(
            "dividend_upcoming",
            "calendar",
            f"Ex-dividend in {ctx.dividend_days}d",
            2.5,
            "DIVIDEND SOON" if ctx.dividend_days <= 7 else None,
        )
    if ctx.earnings and ctx.earnings.get("days_until") is not None:
        d = int(ctx.earnings["days_until"])
        if d == 0:
            add("earnings_today", "calendar", "Earnings TODAY", 3.0, "EARNINGS TODAY")
        elif d <= 3:
            add("earnings_3d", "calendar", f"Earnings in {d}d", 2.5, f"EARNINGS IN {d}D")
        elif d <= 7:
            add("earnings_7d", "calendar", f"Earnings in {d}d", 1.5)

    # --- TECHNICAL ---
    r = rsi(close)
    if r and 48 <= r <= 68:
        add("rsi_bull_zone", "technical", f"RSI {r:.0f}", 2.0)
    elif r and r < 32 and ctx.day_chg_pct > 0:
        add("rsi_oversold_bounce", "technical", f"Oversold bounce RSI {r:.0f}", 2.0, "OVERSOLD BOUNCE")
    elif r and r > 78:
        h.append(FactorHit("rsi_overbought", "risk", f"RSI overbought {r:.0f}", 0, "OVERBOUGHT"))

    hi = i.get("fiftyTwoWeekHigh")
    lo = i.get("fiftyTwoWeekLow")
    pct_rng = pct_52w_range(ctx.price, hi, lo) if hi and lo else None

    if hi and ctx.price >= hi * 0.995:
        add("breakout_52w", "technical", "52-week high breakout", 1.5, "52W BREAKOUT")
        h.append(FactorHit("already_at_high", "risk", "At 52-week high", 0, "AT 52W HIGH"))
    elif hi and ctx.price >= hi * 0.92:
        add("near_52w_high", "technical", "Near 52-week high", 1.0)
    if lo and hi and ctx.price <= lo * 1.15:
        add("near_52w_low", "technical", "Near 52-week low (value zone)", 1.5)

    # --- ENTRY / NEXT-BUY (not chasing extended names) ---
    if pct_rng is not None and 0.68 <= pct_rng <= 0.88:
        add("room_to_run", "entry", f"Room to run ({pct_rng*100:.0f}% of range)", 3.0)
    if pct_rng is not None and pct_rng <= 0.30 and ctx.day_chg_pct >= -2:
        add("deep_value_zone", "entry", f"Value zone ({pct_rng*100:.0f}% range)", 2.5)
    if rsi_turning_up(close):
        add("rsi_turning_up", "entry", "RSI turning up from low", 2.5, "RSI TURN")
    if near_ma_pullback(close, 50):
        add("pullback_50dma", "entry", "Pullback to 50-day MA", 2.5)
    if range_compression(close):
        add("base_compression", "entry", "Tight 20-day base", 2.0)
    if higher_lows(close):
        add("higher_lows", "entry", "Higher lows pattern", 2.0)
    if ctx.rvol >= 1.4 and pct_rng is not None and pct_rng < 0.90:
        add("pre_breakout_vol", "entry", f"Volume building RVOL {ctx.rvol:.1f}x", 2.5)
    if 0 < ctx.ret5d_pct < 8 and -5 < ctx.ret20d_pct < 12:
        add("rs_turn_positive", "entry", "Early RS turn (5d up, 20d muted)", 2.0)
    if len(close) >= 25:
        ma20 = float(close.rolling(20).mean().iloc[-1])
        if ctx.price > ma20 and float(close.iloc[-2]) < ma20:
            add("reclaim_20dma", "entry", "Reclaimed 20-day MA", 2.0)
    ch_pre, _ = cup_handle_score(ctx.hist)
    if 2 <= ch_pre < 4 and pct_rng is not None and pct_rng < 0.88:
        add("cup_forming", "entry", f"Cup forming {ch_pre}/4", 2.5)
    if ctx.earnings and ctx.earnings.get("days_until") is not None:
        ed = int(ctx.earnings["days_until"])
        if 5 <= ed <= 14 and pct_rng is not None and pct_rng < 0.85:
            add("earnings_pre_catalyst", "entry", f"Pre-earnings {ed}d", 2.0)
    short = i.get("shortPercentOfFloat")
    if short and short > 0.12 and ctx.rvol >= 1.3 and ctx.day_chg_pct > 0:
        add("short_squeeze_setup", "entry", f"Short {short*100:.0f}% + vol", 2.5, "SQUEEZE SETUP")
    if pe and vt.get("pe_high") and pe < (vt["pe_low"] + vt["pe_high"]) / 2:
        add("pe_below_sector", "entry", f"P/E {pe:.1f} below sector mid", 1.5)
    target = i.get("targetMeanPrice")
    if target and ctx.price and ctx.price < target * 0.80:
        upside = (target / ctx.price - 1) * 100
        add("below_analyst_target", "entry", f"{upside:.0f}% to target", 2.5)

    # Extension / chase penalties
    if ctx.ret20d_pct >= 25 and pct_rng is not None and pct_rng >= 0.88:
        h.append(FactorHit("extended_run", "risk", f"Extended +{ctx.ret20d_pct:.0f}% 20d", 0, "EXTENDED"))
    if pct_rng is not None and pct_rng >= 0.92 and ctx.ret5d_pct >= 8:
        h.append(FactorHit("chase_risk", "risk", "Chase: high + hot 5d", 0, "CHASE RISK"))
    if ctx.ret5d_pct >= 15:
        h.append(FactorHit("parabolic_move", "risk", f"5d +{ctx.ret5d_pct:.0f}%", 0, "PARABOLIC"))

    ch, _ = cup_handle_score(ctx.hist)
    if ch >= 3:
        add("cup_handle", "technical", f"Cup & handle {ch}/4", 2.5)
    macd = macd_signal(close)
    if macd in ("bullish", "bullish_cross"):
        add("macd_bullish", "technical", f"MACD {macd}", 1.5)
    if macd == "bullish_cross":
        h[-1].alert = "MACD CROSS UP"
    ma = ma_alignment(close)
    if ma in ("full_bull", "bull_stack"):
        add("ma_bull_stack", "technical", f"MA {ma}", 2.0)
    if len(close) >= 50:
        ma50 = float(close.rolling(50).mean().iloc[-1])
        if ctx.price > ma50:
            add("above_50dma", "technical", "Above 50-day MA", 1.5)
        if len(close) >= 200:
            s50 = close.rolling(50).mean()
            s200 = close.rolling(200).mean()
            if s50.iloc[-1] > s200.iloc[-1] and s50.iloc[-2] <= s200.iloc[-2]:
                add("golden_cross_zone", "technical", "Golden cross (50/200)", 2.5, "GOLDEN CROSS")

    # New: explicit DMA/EMA + support/resistance (simple signals that work well for users)
    # DMA = classic 50/200 day moving average. EMA for faster response.
    # Support/resistance near these levels are easy-to-understand buy (support) / sell (resistance) signals.
    ma_info = ma_support_resistance(close)
    if ma_info.get("signal") in ("bullish_trend_support", "bullish_ema_alignment"):
        add("dma_ema_bull_support", "technical", "Price above key DMAs / EMA support", 2.0, "TECH SUPPORT")
    if ma_info.get("signal") == "near_key_ma" and ctx.day_chg_pct > -1:
        # Price hugging a major MA - often acts as support in uptrends
        add("near_dma_support", "entry", "Taking support near 50/200 DMA or 20 EMA", 2.0)
    if ma_info.get("levels"):
        lv = ma_info["levels"]
        if "50DMA" in lv and abs((ctx.price - lv.get("50DMA", ctx.price)) / max(1, lv.get("50DMA",1))) < 0.02:
            add("near_50dma", "technical", f"Near 50 DMA ({lv['50DMA']})", 1.0)
        if "200DMA" in lv and abs((ctx.price - lv.get("200DMA", ctx.price)) / max(1, lv.get("200DMA",1))) < 0.025:
            add("near_200dma", "technical", f"Near 200 DMA ({lv['200DMA']}) - major support/res", 1.5)
    ema20v = ema(close, 20)
    if ema20v and ctx.price > ema20v * 0.98 and ctx.price < ema20v * 1.03:
        add("near_ema20", "technical", "Price near 20 EMA", 1.0)

    # --- VOLUME & MOMENTUM ---
    if ctx.rvol >= 2.5:
        add("rvol_surge", "volume", f"RVOL {ctx.rvol:.1f}x", 3.0, f"RVOL {ctx.rvol:.1f}x")
    elif ctx.rvol >= 1.6:
        add("rvol_above_avg", "volume", f"RVOL {ctx.rvol:.1f}x", 1.5)
    vtrend = volume_trend(volume)
    if vtrend and vtrend >= 1.2:
        add("volume_trend_up", "volume", "Volume trend rising", 1.5)
    if 4 <= ctx.ret5d_pct < 12 and (pct_rng is None or pct_rng < 0.90):
        add("momentum_5d", "momentum", f"5d +{ctx.ret5d_pct:.1f}%", 1.5)
    elif ctx.ret5d_pct >= 8 and pct_rng is not None and pct_rng < 0.85:
        add("momentum_5d", "momentum", f"5d +{ctx.ret5d_pct:.1f}%", 1.0)
    if 8 <= ctx.ret20d_pct < 22:
        add("momentum_20d", "momentum", f"20d +{ctx.ret20d_pct:.1f}%", 1.0)
    if abs(ctx.day_chg_pct) >= 4:
        add("intraday_move", "momentum", f"Day {ctx.day_chg_pct:+.1f}%", 2.0)
    if ctx.day_chg_pct > 0.5 and ctx.rvol >= 1.5:
        add("accumulation_day", "volume", "Accumulation day", 1.5)
    if ctx.day_chg_pct < -1 and ctx.rvol >= 1.8:
        h.append(
            FactorHit(
                "distribution_day",
                "risk",
                f"Distribution day {ctx.day_chg_pct:+.1f}%",
                0,
                "DISTRIBUTION",
            )
        )

    post = i.get("postMarketChangePercent")
    pre = i.get("preMarketChangePercent")
    if post and abs(post) >= 2.5:
        add("post_market_gap", "momentum", f"Post-market {post:+.1f}%", 2.0)
    if pre and abs(pre) >= 2:
        add("pre_market_gap", "momentum", f"Pre-market {pre:+.1f}%", 1.5)

    # --- NEWS & CATALYSTS (text mining) ---
    if ctx.news_count >= 3:
        add("news_burst", "news", f"News burst ({ctx.news_count})", 2.5, "NEWS SPIKE")
    elif ctx.news_count >= 1:
        add("in_news", "news", f"In headlines ({ctx.news_count})", 1.0)

    ni = ctx.news_intel
    sm = ctx.smart_money
    news_map = [
        ("policy_gov", "catalyst", "Govt/PLI/policy tailwind", 2.5, "POLICY"),
        ("order_contract", "catalyst", "Order book / contract news", 2.5, "CONTRACT"),
        ("merger_acquisition", "catalyst", "M&A / acquisition talk", 2.5, "M&A"),
        ("famous_investor", "catalyst", "Notable investor activity", 3.0, "WHALE BUY"),
        ("politician", "catalyst", "Politician trading news", 3.0, "POLITICIAN BUY"),
        ("insider_buy", "catalyst", "Insider/promoter buying", 2.0, "INSIDER BUY"),
        ("analyst_positive", "catalyst", "Analyst upgrade", 2.0),
        ("earnings_positive", "catalyst", "Positive earnings headline", 2.0),
        ("dividend_news", "income", "Dividend announcement news", 1.5),
        ("sector_tailwind", "catalyst", "Sector tailwind news", 1.5),
        ("buyback", "catalyst", "Share buyback news", 2.0, "BUYBACK"),
        ("fda_approval", "catalyst", "FDA / approval news", 2.5, "FDA"),
        ("fii_flow", "catalyst", "FII / DII flow news", 2.0, "FII FLOW"),
        ("turnaround", "catalyst", "Turnaround / recovery news", 2.5, "TURNAROUND"),
        ("new_ceo", "catalyst", "New CEO / leadership", 2.0, "NEW CEO"),
        ("expansion_capex", "catalyst", "Expansion / capex news", 2.0),
        ("partnership", "catalyst", "Partnership / JV", 2.0),
        ("patent_ip", "catalyst", "Patent / IP news", 2.0),
        ("guidance_raise", "catalyst", "Guidance raised", 2.5, "GUIDANCE UP"),
        ("init_coverage", "catalyst", "New analyst coverage", 2.0),
        ("stake_increase", "catalyst", "Stake increase", 2.0),
        ("bulk_block_deal", "catalyst", "Bulk / block deal", 2.0),
        ("qip_fundraise", "catalyst", "QIP / fundraise news", 1.0),
        ("lawsuit_win", "catalyst", "Legal overhang cleared", 1.5),
        ("rate_cut_benefit", "catalyst", "Rate-cut beneficiary", 2.0),
        ("commodity_tailwind", "catalyst", "Commodity tailwind", 1.5),
        ("ai_theme", "catalyst", "AI narrative", 2.0, "AI THEME"),
        ("semiconductor_theme", "catalyst", "Semiconductor theme", 2.0),
        ("export_order", "catalyst", "Export demand news", 2.0),
        ("capacity_expansion", "catalyst", "Capacity expansion", 2.0),
        ("short_squeeze_talk", "catalyst", "Short squeeze narrative", 2.0),
        ("tariff_relief", "catalyst", "Tariff / trade relief", 2.0),
        ("banking_npa_improve", "catalyst", "Bank NPA improving", 2.0),
    ]
    for attr, cat, label, pts, *al in news_map:
        if attr == "famous_investor" and (sm.india_legend or sm.us_legend):
            continue
        if attr == "politician" and (sm.politician_us or sm.politician_india):
            continue
        if getattr(ni, attr, False):
            add(f"news_{attr}", cat, label, pts, al[0] if al else None)

    def _sm_label(kind: str, fallback: str) -> tuple[str, str]:
        hits = [m for m in sm.matches if m.kind == kind]
        if not hits:
            return fallback, fallback
        names = ", ".join(m.display_name for m in hits[:3])
        return f"{names} — smart money buy", hits[0].alert_text()

    if sm.india_legend and ctx.market == "india":
        lbl, al = _sm_label("india_legend", "India legend investor buy")
        add("smart_money_india_legend", "catalyst", lbl, 6.0, al)
    if sm.us_legend and ctx.market == "us":
        lbl, al = _sm_label("us_legend", "US whale / fund buy")
        add("smart_money_us_legend", "catalyst", lbl, 6.0, al)
    if sm.politician_us and ctx.market == "us":
        lbl, al = _sm_label("politician_us", "US politician stock buy")
        add("smart_money_politician", "catalyst", lbl, 5.5, al)
    elif sm.politician_india and ctx.market == "india":
        lbl, al = _sm_label("politician_india", "India politician disclosure")
        add("smart_money_politician", "catalyst", lbl, 5.5, al)
    if sm.foreign_india and ctx.market == "india":
        lbl, al = _sm_label("foreign_india", "Foreign fund buying India")
        add("smart_money_foreign_india", "catalyst", lbl, 5.0, al)
    # Cross-market: US headline on India symbol (ADR / global fund)
    if sm.us_legend and ctx.market == "india" and not sm.india_legend:
        lbl, al = _sm_label("us_legend", "Global whale mention")
        add("smart_money_us_legend", "catalyst", lbl, 4.5, al)

    # --- SECTOR-SPECIFIC BONUSES ---
    if ctx.bucket == "banks" and i.get("returnOnEquity") and i["returnOnEquity"] > 0.12:
        add("bank_roe", "sector", "Bank ROE acceptable", 2.0)
    if ctx.bucket == "technology" and i.get("revenueGrowth") and i["revenueGrowth"] > 0.15:
        add("tech_growth", "sector", "Tech revenue growth", 2.0)
    if ctx.bucket == "utilities" and dy and dy > 0.03:
        add("utility_yield", "sector", "Utility dividend yield", 2.0)
    if ctx.bucket in ("india_defense_psu", "industrials") and ni.policy_gov:
        add("india_defense_policy", "sector", "Defense/infra policy news", 2.5)
    if ctx.bucket == "energy" and fcf and fcf > 0:
        add("energy_fcf", "sector", "Energy positive FCF", 1.5)

    return h


def evaluate_factors(ctx: ScanContext) -> tuple[float, list[FactorHit], list[str], dict]:
    """
    Returns (buy_score 0-100, hits, alerts, metrics_dict).
    Primary score favors early entry; quality_score is full factor sum.
    """
    hits = _hits(ctx)
    positive = [x for x in hits if x.points > 0]
    breakdown = build_factor_breakdown(hits, ctx.market)
    for item in breakdown:
        if item.get("status") == "pass" and item.get("points"):
            fid = item["id"]
            item["weight"] = factor_weight(fid)
            item["tier"] = tier_label(fid)
            item["weighted_points"] = weighted_points(fid, item["points"])
    factors_hit, factors_applicable = count_applicable(breakdown)
    hi = ctx.info.get("fiftyTwoWeekHigh")
    lo = ctx.info.get("fiftyTwoWeekLow")
    pct_rng = pct_52w_range(ctx.price, hi, lo)
    buy_score, quality_score, ext_pen, top_weighted, enriched = _compute_scores(hits, pct_rng)
    score = buy_score
    alerts = [x.alert for x in hits if x.alert]
    if ctx.smart_money.primary_alert and ctx.smart_money.primary_alert not in alerts:
        alerts.insert(0, ctx.smart_money.primary_alert)
    signals = [x.label for x in positive]

    by_category: dict[str, int] = {}
    for x in positive:
        by_category[x.category] = by_category.get(x.category, 0) + 1

    metrics = {
        "price": round(ctx.price, 4),
        "day_chg_pct": round(ctx.day_chg_pct, 2),
        "ret5d_pct": round(ctx.ret5d_pct, 2),
        "ret20d_pct": round(ctx.ret20d_pct, 2),
        "rvol": round(ctx.rvol, 2),
        "rsi": round(rsi(ctx.hist["Close"]), 1) if len(ctx.hist) > 15 else None,
        "sector": ctx.sector,
        "industry": ctx.industry,
        "sector_bucket": ctx.bucket,
        "pe": ctx.metric("trailingPE"),
        "pb": ctx.metric("priceToBook"),
        "peg": ctx.metric("pegRatio"),
        "fcf": ctx.metric("freeCashflow"),
        "div_yield": ctx.metric("dividendYield"),
        "inst_pct": ctx.metric("heldPercentInstitutions"),
        "insider_pct": ctx.metric("heldPercentInsiders"),
        "short_pct": ctx.metric("shortPercentOfFloat"),
        "news_24h": ctx.news_count,
        "factors_hit": factors_hit,
        "factors_total": factors_applicable,
        "factors_catalog_total": FACTORS_TOTAL,
        "factors_by_category": by_category,
        "name": ctx.metric("shortName", ctx.symbol),
        "earnings_date": (ctx.earnings or {}).get("earnings_date"),
        "days_until_earnings": (ctx.earnings or {}).get("days_until"),
        "dividend_days": ctx.dividend_days,
        "buy_score": buy_score,
        "quality_score": quality_score,
        "extension_penalty": round(ext_pen, 1),
        "pct_52w_range": round(pct_rng * 100, 1) if pct_rng is not None else None,
        "entry_factors": sum(1 for x in positive if x.id in ENTRY_FACTOR_IDS),
        "is_extended": ext_pen >= 10 or (pct_rng is not None and pct_rng >= 0.92),
        "weighted_total": round(sum(x["weighted_points"] for x in enriched), 1),
        "top_weighted_factors": top_weighted,
        "smart_money": ctx.smart_money.to_metrics(),
        "has_smart_money": bool(ctx.smart_money.matches),
    }

    factor_details = enriched
    return score, hits, alerts, {
        **metrics,
        "factor_details": factor_details,
        "factor_breakdown": breakdown,
        "signals": signals,
    }