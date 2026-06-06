# Market Pulse — 76 Factor Scorecard

Each stock is scored against **76 factors** in the master catalog (US + India). Per stock, ~65–70 checks apply (US-only or India-only factors show as N/A). A factor **passes** when data supports it.  
Final score (0–100) = weighted sum of passed hits, capped at 100.

**UI:** Click the blue **Factors** pill on Hot Movers to see every check (pass / fail / risk).

**Data sources today:** Yahoo Finance fundamentals, calendar (earnings/dividends), RSS news text.  
**Planned upgrades:** NSE promoter/pledge, FII/DII, Form 4 feeds, dedicated M&A wire.

---

## Fundamental & cash (8)

| ID | Factor |
|----|--------|
| fcf_positive | Positive free cash flow |
| operating_cf_positive | Positive operating cash flow |
| net_margin_strong | Net margin > 10% |
| gross_margin_strong | Gross margin > 35% |
| revenue_growth | Revenue growth > 10% |
| earnings_growth | Earnings growth > 10% |
| roe_strong | ROE > 15% |
| roa_positive | ROA > 5% |

## Valuation — sector-aware PE/PB (5)

| ID | Factor |
|----|--------|
| pe_sector_ok | P/E inside sector band |
| pb_sector_ok | P/B key metric (banks, insurance, real estate) |
| pb_reasonable | P/B reasonable (non-bank) |
| peg_attractive | PEG < 1.5 |
| ev_revenue_ok | EV/Revenue < 5 |

**Sector buckets:** banks, insurance, real estate, technology, healthcare, utilities, energy, industrials, india_defense_psu, general.

## Financial health (3)

| ID | Factor |
|----|--------|
| debt_manageable | Debt/Equity < 80 |
| liquidity_current_ratio | Current ratio > 1.2 |
| liquidity_quick_ratio | Quick ratio > 1.0 |

## Ownership (3 US / India)

| ID | Factor |
|----|--------|
| institutional_holding | US: institutions > 45% |
| insider_holding | Insider/promoter > 25% (India proxy) |
| low_short_interest | US: short float < 8% |

## Calendar — earnings & dividends (4)

| ID | Factor |
|----|--------|
| dividend_yield | Yield > 1.5% |
| dividend_upcoming | Ex-dividend within 14 days |
| earnings_today / earnings_3d / earnings_7d | Results within 0–7 days |

## Technical (7)

| ID | Factor |
|----|--------|
| rsi_bull_zone | RSI 48–68 |
| rsi_oversold_bounce | RSI < 32 + green day |
| near_52w_high | Price ≥ 92% of 52w high |
| near_52w_low | Near 52w low (value) |
| cup_handle | Cup & handle pattern |
| macd_bullish | MACD bullish / cross |
| ma_bull_stack | Price above rising MAs |

## Volume & momentum (7)

| ID | Factor |
|----|--------|
| rvol_surge | Relative volume ≥ 2.5x |
| rvol_above_avg | RVOL ≥ 1.6x |
| volume_trend_up | 10d volume trend rising |
| momentum_5d | 5-day return ≥ 8% |
| momentum_20d | 20-day return ≥ 15% |
| intraday_move | Day move ≥ 4% |
| post_market_gap / pre_market_gap | Extended hours gap |

## News & catalysts (10)

| ID | Factor |
|----|--------|
| news_burst | 3+ headlines in window |
| in_news | 1+ headline |
| news_policy_gov | Govt / PLI / policy |
| news_order_contract | Orders / tenders / contracts |
| news_merger_acquisition | M&A language |
| news_famous_investor | Buffett, ARK, well-known India investors |
| **smart_money_india_legend** | **S+** Kela, Kacholia, Kedia, Jhunjhunwala, etc. + buy headline |
| **smart_money_us_legend** | **S+** Buffett, Ackman, ARK, Icahn, etc. + buy headline |
| **smart_money_politician** | **S+** Pelosi, Congress/STOCK Act, India MP disclosure |
| **smart_money_foreign_india** | **S** FII / US fund raising India stake |
| news_politician | Politician trading news (generic; superseded when named match) |
| news_insider_buy | Insider/promoter buying in news |
| news_analyst_positive | Upgrades / PT raises |
| news_earnings_positive | Beat / strong quarter headlines |
| news_dividend_news | Dividend announcement |
| news_sector_tailwind | Sector rally / capex news |

## Sector bonuses (5)

| ID | Factor |
|----|--------|
| bank_roe | Banks: ROE > 12% |
| tech_growth | Tech: revenue growth > 15% |
| utility_yield | Utilities: yield > 3% |
| india_defense_policy | Defense PSUs + policy news |
| energy_fcf | Energy: positive FCF |

## Risk flags (not scored — alerts only)

| ID | Alert |
|----|--------|
| high_short | Short interest > 20% |
| rsi_overbought | RSI > 78 |

---

## India vs US differences

| Topic | US | India |
|-------|----|-------|
| Promoter holding | `heldPercentInsiders` proxy | Same field (Yahoo); full pledge needs NSE |
| Valuation | PE + PEG emphasis | Higher PE bands; PB for banks |
| Policy | Federal, CHIPS, defense | PLI, Make in India, PSU orders |
| Short interest | Yes | Rare on Yahoo |

## Comparison

Stocks are **ranked by composite score** on the Hot Movers table. Click a row to see **which factors fired** and category tags (fundamental, valuation, news, etc.).