# Market Pulse

Real-time **US + India** stock scanner with:

- 24/7 background crawlers (prices + RSS news)
- **20+ auto signals** (RSI, RVOL, cup/handle, MACD, MA stack, FCF, news burst, AH/pre-market, etc.)
- Live WebSocket dashboard with sparklines
- SQLite history for news and high-score snapshots

## Quick start

```bash
cd market-pulse
chmod +x run.sh
# After any requirements change (e.g. added lxml for full S&P 500 universe):
rm -rf .venv
./run.sh
```

Open **http://127.0.0.1:8765**

**Note on universe size & earnings:** The app now uses an expanded static fallback + Wikipedia scrape (requires `lxml`). With a fuller list of liquid names the "Earnings (7d)" list will surface more names when they have calendar data. In any 7-day window only a modest number of companies report — that's normal. Add tickers to `data/us_extra.txt` / `data/india_extra.txt` to watch more.

## Docker (24h operation)

```bash
docker compose up -d --build
```

## Architecture

```
RSS News Feeds + Google News (broad web aggregation) ──► News Crawler (tagging + catalyst NLP) ──► SQLite + symbol tagging
                         │
Yahoo Finance  ◄── Price Crawler (batched, ~600+ symbols)
                         │
                  Signal Engine (weighted score 0–100)
                         │
                  WebSocket broadcast (2s) ──► Browser UI
```

## 100+ factor scorecard (76+ in core catalog + entry/risk)

Every stock is scored on a large catalog of factors (fundamentals, sector-aware valuation, ownership, dividends/earnings calendar, technicals, volume/momentum, news catalysts, smart-money legends, sector bonuses, entry setups, and risk penalties).  
See **[docs/FACTORS.md](docs/FACTORS.md)** for the full list and weighting tiers (S+ / S / A / B / C / D).

- Code: `app/engine/factor_registry.py`, `app/engine/sector_rules.py`, `app/engine/news_intel.py`
- UI: **Factors** column (e.g. `17/42`) and detail breakdown by category

## Legacy signals (extensible in `app/engine/signals.py`)

| Signal | What it detects |
|--------|-----------------|
| Big day move | Intraday \|change\| ≥ 2.5–5% |
| 5d / 20d momentum | Short-term trend strength |
| RVOL | Volume vs 10-day average |
| RSI zone | 48–68 bullish; \<32 bounce |
| Near 52-week high | Breakout proximity |
| Cup & handle | 4-point pattern heuristic |
| Positive FCF / revenue growth | Fundamentals |
| Post/pre market | Extended hours gap |
| News burst | Multiple headlines tagged to symbol |
| Earnings proximity | Results within 7 days (calendar crawler) |
| MACD | Bullish / crossover |
| MA alignment | 20/50/200 stack |
| Volume trend | Rising participation |

Edit weights in `config.yaml` under `signals.weights`.

## Universe

- **US:** S&P 500 (Wikipedia) + Nasdaq-100 sample + `data/us_extra.txt`
- **India:** Nifty 50 + extended liquid list + `data/india_extra.txt`

To scan **more** symbols, add tickers to the extra files or set `batch_size` / `price_scan_interval_sec` in config (watch Yahoo rate limits).

## API

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard UI |
| `GET /api/snapshot` | Full hot list + news |
| `GET /api/symbol/{SYM}` | One symbol |
| `GET /api/news` | Stored + live news |
| `GET /api/earnings?days=7` | Earnings in next N days |
| `WS /ws` | Real-time updates |

## Database & disk usage

- **Engine:** [SQLite](https://www.sqlite.org/) — single file at `data/market_pulse.db` (not Postgres/MySQL).
- **Live UI data** is mostly in memory; the DB stores news history, high-score scan snapshots, and earnings rows.
- **Automatic cleanup** (config `retention`):
  - News older than **7 days** → deleted
  - Scan snapshots older than **3 days** → deleted
  - Per symbol: keep at most **30** snapshot rows
  - Earnings outside the 7-day window → deleted
  - Runs on **startup** and every **12 hours** (`VACUUM` to shrink the file)

Tune in `config.yaml` if you want longer history or more aggressive cleanup.

## Limitations (honest)

- **Not** a sub-second HFT feed — uses free Yahoo Finance + RSS + Google News RSS (90s default full scan).
- **True “all stocks”** tick data requires paid APIs (Polygon, NSE, Breeze, etc.).
- News symbol matching is keyword-based (plus Google-aggregated web results) — can miss or false-positive. The Google News feeds pull from thousands of underlying sources (the value beyond manually checking 5-10 sites).
- Pattern detection is heuristic, not a certified charting platform.

## Upgrading to production

1. Add paid price feed (Polygon / Finnhub / NSE official).
2. Add Redis for multi-worker scaling.
3. Add sentiment NLP on headlines.
4. Add earnings calendar API.

## Disclaimer

Not financial advice. For research and education only.