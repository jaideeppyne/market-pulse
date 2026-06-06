# Market Pulse

[![GitHub](https://img.shields.io/badge/GitHub-jaideeppyne%2Fmarket--pulse-181717?logo=github)](https://github.com/jaideeppyne/market-pulse)

Real-time **US + India** stock scanner with:

- 24/7 background crawlers (prices + RSS + Google News aggregation from thousands of sources)
- **140-factor engine** with tiered scoring (S+ named smart money / politicians / FII at 6.5×), explicit entry bonuses + extension penalties, sector-aware valuation
- Buy score (next-entry rank) vs Quality score (full checklist)
- Live WebSocket dashboard + sparklines
- On-demand full-engine analysis for *any* ticker (search box reuses 100% of the same engine)
- **My List** watch with local persistence + score history
- **S+ Radar** for named legend/politician/FII activity
- In-app + browser alerts for high-conviction setups, new smart money hits, pre-earnings catalysts
- Auto trade thesis + risk bullets + local position sizer from the factor breakdown
- CSV export + Markdown thesis copy
- SQLite snapshots for historical edge / backtest views (/api/edge) + per-symbol score history
- Rich factor checklist modal (pass/fail/risk/weight/tier/description) with filters

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

## GitHub

Source code: https://github.com/jaideeppyne/market-pulse

This repo contains the full application (backend + frontend). The "website" (dashboard) requires the Python server to be running.

### Deploy the live app

The full experience (live crawlers + WebSocket updates) needs a server:

- **Easiest (recommended)**: [Render](https://render.com), [Railway](https://railway.app), or [Fly.io](https://fly.io)
- Use the included `Dockerfile` + `docker-compose.yml`
- Set environment as needed (no secrets required for the free data sources)
- The server listens on port 8765 by default (configurable in `config.yaml`)

### GitHub Pages (UI only)

You can host just the static frontend on GitHub Pages for a visual preview (no live data or API calls). Point Pages to the `/frontend` folder (or copy `index.html` + assets to a `docs/` or `gh-pages` branch). The UI will be non-functional without a backend.

## Architecture

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
| `GET /api/symbol/{SYM}` or `/api/analyze/{SYM}` | Full engine analysis for any ticker (reuses the 140-factor path) |
| `GET /api/news` | Stored + live news |
| `GET /api/earnings?days=7` | Earnings in next N days |
| `GET /api/edge?days=2&min_score=55` | Recent strong snapshots for backtest/edge validation |
| `GET /api/snapshots/{SYM}` | Per-symbol snapshot history (score curves) |
| `GET /api/factors` | Catalog + weights + smart money registry |
| `WS /ws` | Real-time updates (used for alerts + live UI) |

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

## New trader experience features (implemented)

- My List (watch + local score history + deltas)
- S+ Radar (named smart money / politician / FII live feed)
- Alerts (in-app bell + browser Notification for high buy, new S+, pre-earnings, bursts)
- Auto Trade Thesis + risks + local position sizer in every detail/analysis
- Export (CSV hot/watch) + one-click Markdown thesis copy for journals
- Enhanced gauges (high-conviction count, S+ hits, news activity)
- Keyboard power: / search, w=watch, f=factors, e=export
- PWA manifest (installable)
- /api/edge + /api/snapshots for historical validation / backtesting of the engine signals
- More India catalyst patterns (bulk/block, promoter stake)

## Disclaimer

Not financial advice. For research and education only.