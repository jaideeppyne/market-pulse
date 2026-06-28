# Market Pulse — World-Class Review & Roadmap

**Date:** 2026-06-16
**Scope:** Full codebase — backend (`app/`, ~7.5k LOC Python), frontend (`web/` React + Redux + Vite), data layer (`db.py`, crawlers, `universe.py`), tests, deploy/infra.
**Method:** Four independent deep-dive reviews (engine correctness, security/robustness, frontend/UX, data/infra/testing), with the highest-stakes findings verified first-hand against source.

---

## 0. Verdict (TL;DR)

Market Pulse is an **ambitious, genuinely impressive solo/small-team build**: a reusable 140-factor scoring engine, a live WebSocket terminal, US+India coverage, a smart-money registry, an ML overlay, a backtest data layer, and one-command deploys. The *surface area* of a world-class product is already here. Architecturally it is coherent: one engine powers live scans, ad-hoc analysis, discovery, and exhaustive jobs alike.

But it is **not yet world-class**, and the gap is not "more features." For a stock scanner, **trust is the product** — and right now the engine emits signals that are, in places, *fabricated or mathematically incorrect*, the public deploy ships **unauthenticated with a spoofable admin bypass and a one-request DoS**, and the **entire scoring engine has 0% test coverage with no CI**. A user cannot currently distinguish a real edge from a bug.

The path to world-class is therefore, in order:

1. **Stop emitting false signals** (correctness + credibility) — this is existential for a financial tool.
2. **Lock the doors** (security) before any wider deployment.
3. **Prove the edge** (testing, backtest→calibration loop) — turn "140 factors" from a marketing number into a measured, calibrated model.
4. **Then** make it beautiful and fast (UX) and build a moat (data + validation no competitor has).

The rest of this document is the evidence and the plan.

---

## 1. What Market Pulse is today

```
RSS + Google News (48 feeds) ─► news_crawler ─► tag symbols ─┐
SEC Form 4 / EDGAR ─► event/insider_crawler ─► investor_events│
Yahoo Finance (yfinance) ─► price_crawler ──────────────────►├─► Engine (analyze_symbol)
Earnings calendar/RSS ─► earnings_crawler ──────────────────►│    ├─ ScanContext (indicators, news NLP, smart-money)
                                                              │    ├─ factor_registry (140+ checks)
                                                              │    ├─ scoring (buy_score vs quality_score)
                                                              │    └─ ml_intel (heuristics + IsolationForest)
                                                              ▼
                                            AppState (in-memory) + SQLite (snapshots/news/events)
                                                              ▼
                                   FastAPI: REST + WebSocket broadcast (event-driven)
                                                              ▼
                                   React + Redux Toolkit + RTK Query terminal (web/)
```

**Strengths to preserve (do not regress these):**
- **One engine, every path.** Live hot list, `/api/analyze/{sym}`, discover, and exhaustive jobs all reuse `analyze_symbol`. This is the right architecture and a real asset.
- **RTK Query frontend** with correct cache tags/invalidation; route-level code splitting.
- **A real backtest *data* layer** (`scan_snapshots` + `recent_strong_snapshots_with_outcomes` computing forward returns) — the raw material for a self-validating engine already exists.
- **A decent API/persistence test suite** (`test_api_p0.py`) doing real DB round-trips — proof the team *can* test well.
- **Two-market (US+India) ambition** with India-heavy news coverage is a genuine differentiator vs US-only tools.

**The honest gap:** the product is ~80% *feature-complete* against its own README, but much closer to ~40% *trustworthy/production-grade*. World-class is the second number.

---

## 2. The core thesis: trust is the product

Bloomberg, TradingView, and Koyfin win because users *believe the numbers*. A scanner that occasionally invents a "Nancy Pelosi bought AAPL" signal, or whose flagship 0–100 score saturates so the top 30% of names are indistinguishable, is not competing on the same axis no matter how many factors it advertises.

So the review is organized by **severity to trust and safety first**, then engineering quality, then polish. Every finding below is cited to `file:line`.

---

## 3. Findings by severity

### 3.1 🔴 P0 — Credibility & correctness killers (the engine is lying in places)

These directly corrupt the signals users act on. Fix before anything else.

| # | Finding | Location | Why it's P0 |
|---|---------|----------|-------------|
| **E1** | **Fabricated political/insider aliases.** `"PELOSI":"AAPL"`, `"TRUMP":"TSLA"`, `"IVANKA":"TSLA"`, `"GADKARI":"ADANIPORTS.NS"` are hardcoded, admittedly-fake (`"example; real would resolve dynamically"`). Any headline mentioning Trump tags TSLA as an **S+ politician catalyst at 6.5× weight**. | `universe.py:421-423` | The app manufactures high-conviction smart-money signals from thin air. For a tool touching investment decisions this is a credibility and potential-liability disaster. |
| **E2** | **`buy_score` residual can go *negative* for the very signals it should reward.** `catalyst_w` accumulates *boosted* smart-money points (`wp * SMART_MONEY_BUY_BOOST`), but `buy_raw` then subtracts `(quality_w − entry_w − catalyst_w) * 0.85` — and `quality_w` only added the *unboosted* `wp`. A strong smart-money/catalyst name can have this term go negative, so the hit **lowers** the buy score. | `scoring.py:42-43, 73-78` | The core ranking number has an inverted-contribution bug for the flagship feature (smart money). |
| **E3** | **Fake tickers minted into scoring from RSS earnings.** `_parse_earnings_from_rss` does `re.findall(r'\b([A-Z]{2,10}(?:\.NS)?)\b', text.upper())` then writes `sym+".NS"` — so "RESULTS", "MARKET", "TODAY" become `RESULTS.NS` earnings rows feeding the `earnings_proximity` factor (weight 10). Dates default to current month, day clamped ≤28. | `earnings_crawler.py:136-174` | Garbage rows pollute the earnings panel and scoring. |
| **E4** | **RSI/ADX/MACD are not the standard formulas.** RSI uses a simple rolling mean (Cutler's), not Wilder smoothing; ADX uses plain `rolling().mean()` with a too-short warm-up (`period+1` vs the required `2*period−1`); MACD needs only 35 bars so EMA26 isn't warmed up. Thresholds (RSI 48–68, <32, >78) were tuned against *standard* RSI, so every RSI/ADX gate mis-fires. | `indicators.py:10-14, 19-32, 252-268` | Dozens of technical factors key off thresholds that don't mean what they're tuned to mean. |
| **E5** | **The 0–100 score saturates and stops being monotonic at the top.** `quality_score = min(100, quality_w*0.38)`, `buy_score = clip(buy_raw*0.42, 0, 100)`. A single S+ hit can already approach the cap, so strong names pile up at 100 and become **indistinguishable** — and fundamentals stop mattering at the top end. Scale constants are hand-tuned, not derived. | `scoring.py:71-79`, `factor_weights.py:134-138` | The flagship ranking can't separate the names that matter most. |
| **E6** | **Severe factor double-counting → "140 factors" is marketing, not 140 independent signals.** MA-proximity counted up to 5× (`above_50dma`+`ma_bull_stack`+`dma_ema_bull_support`+`near_50dma`+…), oversold 4× (RSI/stoch/CCI/BB), volume 3–4×, insider buys via 3 parallel paths. Correlated clusters all add positive weighted points, multiplicatively boosting names that trip one cluster. | `factor_registry.py:173-319, 357-369` | The score over-weights whatever cluster a name happens to trip; effective dimensionality ≪ 140. |
| **E7** | **ML overlay is mislabeled as probability and is batch-relative.** `opportunity_probability` is a hand-invented logistic (`z = -2.2 + buy/34 + …`) presented as a calibrated %. `IsolationForest` is fit per-batch on the same rows it scores, normalized within-batch, with features that include the very `buy_score`/`quality_score` being "explained" — so the "unusual" score changes with whichever peers happened to be in the batch. | `ml_intel.py:85-107, 120-135` | "AI confidence" numbers imply rigor that doesn't exist; same stock scores differently across scans. |
| **E8** | **Lookahead / partial-bar ambiguity.** Nothing enforces whether `hist`'s last bar is a *completed* daily bar. If intraday, RVOL/`day_chg`/breakout read a partial bar (RVOL low mid-session, spikes at close); 52w-range comes from `info` while breakout compares against `ctx.price` — inconsistent timebases / circular. | `context.py:50-64`, `factor_registry.py:177-184`, `indicators.py:85-92` | Determines whether the whole engine has subtle lookahead; signals mean different things by feed timing. |

> Several smaller correctness items (volume_trend off-by-one `indicators.py:85-92`, cup-handle slice `indicators.py:43`, `ret5d` `>`/`>=` off-by-one `context.py:56-61`, uncatalogued `news_*` factors scoring silently `factor_registry.py:415`) compound the above.

### 3.2 🔴 Security — the critical trio (do not deploy publicly until fixed)

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| **S1** | **Spoofable localhost admin bypass.** uvicorn runs `proxy_headers=True` with default `forwarded_allow_ips="*"`, so `request.client.host` is taken from client-supplied `X-Forwarded-For`. The write guard trusts `127.0.0.1`. A remote attacker sends `X-Forwarded-For: 127.0.0.1` and passes `_assert_write_allowed`. | `main.py:286-288, 306, 1310` | Remote unauthenticated **write** access (watchlist/portfolio/alert mutations) on any deploy without a write key. |
| **S2** | **No write key in *any* deploy artifact.** `MARKET_PULSE_WRITE_KEY` is absent from `render.yaml`, `railway.toml`, and both compose files. Default public deploy ships with no key; all reads fully open. | deploy configs; `main.py:291-311` | Insecure-by-default; combined with S1 = open admin. |
| **S3** | **One-request, multi-hour DoS — unauthenticated.** `POST /api/full_exhaustive_scan` and `GET /api/discover` skip `_assert_write_allowed`. Each POST spawns a new thread + task with **no single-flight guard**; the scan sleeps 5s/symbol over ~500–700 symbols (~40+ min) and hammers Yahoo. N requests = N concurrent multi-hour scans → thread exhaustion, memory blowup, Yahoo IP ban. `/api/discover` `extra` is attacker-controllable. | `main.py:1080-1164, 1176-1225` | Trivial resource-exhaustion DoS + provider ban. |

**Supporting security issues (High/Med):** synchronous `yf.download` blocking the event loop in `get_regime`/`/api/edge` (`main.py:842-854`, `db.py:535`); loose symbol validation into yfinance via `{symbol:path}` (`main.py:356-368`); no CORS/security headers/CSRF; Docker runs as **root** with no `.dockerignore` (bakes `.venv`, `.git`, dev DB into the image); `state.jobs`/`state.symbols` grow unbounded (memory DoS via `/api/symbol/<random>` spam); bare `except:` swallowing errors app-wide.

> ✅ Confirmed *good*: all SQL is parameterized (no injection), no secrets committed, DB and the 9.8MB `market-pulse.log` are git-ignored. Symbol/limit validation is solid on the *write/list* endpoints (just not the read path).

### 3.3 🟠 Reliability & concurrency

- **SQLite without WAL or `busy_timeout`.** 8 concurrent async loops + request handlers + a 12-hour `VACUUM` (exclusive lock, full rewrite) all hit one file in default rollback-journal mode. Concurrent writers get `database is locked`; inserts have no try/except so data is silently dropped. **(`db.py` — all 29 connect sites; `:419`)** — *highest-probability production failure.*
- **Connection-per-call** (29 inline `aiosqlite.connect`), no pooling, no `executemany` for the hot snapshot-insert path.
- **`asyncio.run()` inside a thread inside an async endpoint** for exhaustive scans — fragile event-loop nesting. (`main.py:1204-1208`)
- **No retry/backoff** on yfinance; rate-limits silently empty whole batches; quarantine logic can mistakenly blacklist valid symbols during a provider-wide outage. (`price_crawler.py:78-80`, `scanner_loop.py:58-80`)
- **Heavyweight `/api/health`** builds a full snapshot under lock on every 30s probe — can time out and trigger false restarts. (`main.py:1254-1260`)
- **Serial WebSocket broadcast** with per-send `await` — one slow client head-of-line-blocks all others. (`main.py:96-128`)

### 3.4 🟠 Data quality

- **News dedup is exact-URL only** — Google News rewrites the same story under many tracking URLs, inflating the `news_burst` factor (weight 14, the highest). In-memory hit counts increment *before* the insert, so duplicates inflate even when the DB rejects them. (`db.py:26`, `news_crawler.py:70-74`)
- **Ticker matching is substring/regex over thousands of tickers** → constant English-word collisions (`ALL`, `IT`, `ON`, `KEY`, `CAR`…). Band-aided with a hardcoded blocklist; structurally fragile. (`universe.py:451-461`)
- **Static universe lists are stale**: dead/renamed tickers (`FB`, `TWTR`, `ATVI`, `SIVB`, `MINDTREE.NS`, `MOTHERSUMI.NS`…) waste scan slots and trigger quarantine; `US_BROADER` repeats names dozens of times. (`universe.py:11-159, 276-293`)
- **NSE EQUITY_L.csv fetch silently 403s** (no browser headers) → "all India stocks" is in practice the static ~400 names, with **no logging** of the fallback. `build_universe` also runs blocking network I/O synchronously in `lifespan`, stalling startup. (`universe.py:347-388`, `main.py:235`)
- **Two overlapping insider crawlers**; the *worse* stub (emits `symbol:None`, hardcoded name, resolver is `pass`) is the one on the 30s fast path, while the real Form-4 XML parser runs elsewhere. (`insider_crawler.py:12-65` vs `event_crawler.py:83-204`)
- **Stale `days_until`** drives earnings retention — computed once at insert, never recomputed, so cleanup deletes/keeps the wrong rows. (`db.py:281-288, 411-415`)
- **Single unofficial data source (yfinance)** behind everything, pinned `>=` with no lockfile — a Yahoo-side or yfinance change silently breaks earnings/price in a fresh deploy. SEC User-Agent is a placeholder `example.com` (against SEC fair-access). (`event_crawler.py:21`)

### 3.5 🟡 Frontend & UX

- **Re-render firehose (headline FE issue).** Every WS tick replaces `live.data` wholesale; with **zero memoization anywhere**, four components each independently re-derive the full hot pool (dedup + filter + sort of ~220 rows) and the table repaints all rows + sparklines — several times/second on an active scan. (`HotTable.jsx:34-37`, `StatCards.jsx:24-33`, `CommandCenter.jsx:52-54`, `Topbar.jsx:24`)
- **Modal a11y blockers:** no Escape-to-close, no body scroll-lock (the `.modal-open` CSS exists but is never applied), no focus trap/restore. Clickable `<tr>`/`<div>` rows across every table are **not keyboard-operable** (no `role`/`tabIndex`/`onKeyDown`). (`FactorModal.jsx:40-43`; all table components)
- **No initial-load state.** Nothing calls the `snapshot` query; until the first WS push the dashboard shows zeros with no skeleton.
- **Silent failures.** A `toast` action exists in `uiSlice.js:34` but is never dispatched/rendered; mutation errors are `.catch(()=>{})` or a raw `window.alert`. The bell button shows a badge but has no `onClick` (dead feature).
- **WS middleware:** flat 2s reconnect (no backoff), `reconnectTimer` never cleared on disconnect, no client-side liveness detection (a half-open socket shows "Live" forever).
- **Light-theme contrast bugs** from dark-theme inline hex colors bleeding through; the `seen` dedup map grows unbounded (slow store leak); two divergent `hasSmartMoney` regexes can disagree.
- **Committed build output.** `frontend/` (hashed minified bundles) is git-tracked and regenerated by `vite build` (`outDir: ../frontend`), producing churn-heavy minified diffs and the deletions currently sitting in `git status`. (`vite.config.js:11`)
- **Missing for a "terminal":** real charts (only tiny sparklines), number formatting (raw `1234.5678901`), persisted UI state / deep-linking, Cmd-K palette, the price flash-on-change animations (`row-up`/`row-down` keyframes exist but are never applied).

### 3.6 🟡 Engineering hygiene (the force-multiplier gap)

- **No CI at all** (no `.github/`), yet `render.yaml` has `autoDeploy: true` → untested code ships to prod on every push.
- **Scoring engine is 0% tested** — `signals.py`, `scoring.py`, `indicators.py`, `factor_*`, `news_intel`, `ml_intel`, `sector_intel` have no tests. The product's entire value (the score) has no regression protection. (The API/DB suite is good — extend that discipline to the engine.)
- **No lint / format / type-check** (no ruff/black/mypy/eslint config), despite heavy type hints and many bare `except:`.
- **`>=`-only deps, no lockfile** → non-reproducible builds; Python 3.9 vs 3.11 drift.
- **No migration framework** — only an ad-hoc `ALTER TABLE earnings`; any new column on other tables silently breaks existing DBs. No `PRAGMA user_version`.
- Stray artifacts: untracked `.server.pid`, a duplicate `.venv 2/`.

---

## 4. What "world-class" means here

Market Pulse sits at the intersection of three categories. World-class = matching the table stakes of each **and** owning a defensible niche none of them fully serve:

| Category | Exemplars | Table stakes to match | Market Pulse's wedge |
|----------|-----------|------------------------|----------------------|
| Pro terminal | Bloomberg, Koyfin | trustworthy data, real charts, speed, density | — |
| Charting/social | TradingView | beautiful UX, alerts, community | — |
| Quant/scanner | Finviz, Trade Ideas | screeners, backtested factors | — |
| **The wedge** | *(nobody owns this well)* | — | **US + India**, **named smart-money/insider/FII tracking**, and a **transparent, self-validating, calibrated factor engine** that shows its own hit-rate. |

The wedge is the moat. But a moat built on fabricated/uncalibrated signals is a liability. So the build order makes the wedge *credible* before it makes it *pretty*.

**Definition of world-class for this product:**
1. Every signal is real, sourced, and reproducible (no fabricated aliases; news/insider/FII data is attributable to a filing or article).
2. The flagship score is **calibrated**: "buy_score 80" means a measurably higher forward hit-rate than "buy_score 60", shown in-app from the backtest layer.
3. Secure, multi-user, reliable enough to leave running unattended.
4. A terminal that feels instant (memoized, virtualized, flash-on-tick) with real charts.
5. Engineering you can move fast on: CI-gated, tested engine, reproducible builds, observable in prod.

---

## 5. The roadmap

Five phases. Each maps directly to the findings above. Effort is rough (1 focused engineer); parallelizable where noted. **Phases 0–1 are non-negotiable prerequisites for any public launch.**

### Phase 0 — Stop the bleeding (trust + security) · ~1–2 weeks · 🔴 blocker

*Goal: the app no longer emits false signals and can't be trivially abused.*

1. **Delete fabricated aliases (E1).** Remove the politician/CEO/relative alias map entirely. Re-introduce smart-money/politician detection **only** when backed by a real source (an actual EDGAR Form 4, a sourced 13F, a STOCK-Act disclosure feed, or an article that *names the filing*). Until then, no politician signals. *(half day)*
2. **Fix the `buy_score` residual (E2).** Attribute each factor to exactly one bucket (entry / catalyst / other) and compute `other_w` only over factors not already in entry/catalyst; never let a positive hit reduce the score. Add a unit test asserting monotonicity (adding a positive factor never lowers buy_score). *(1 day)*
3. **Kill the fake-ticker earnings parser (E3).** Only emit an earnings row when a *known-universe* ticker is explicitly present **and** a full date parses; otherwise drop. *(half day)*
4. **Security trio (S1/S2/S3):**
   - Set `forwarded_allow_ips` to the known proxy only (never `*`); derive "local" from the socket peer, not `X-Forwarded-For`.
   - Require an API key for *all* writes **and** the expensive compute endpoints; fail-closed if unset in non-local mode. Template `MARKET_PULSE_WRITE_KEY` into every deploy config + a `.env.example`.
   - Add a single-flight guard on `full_exhaustive_scan`/`discover` (reject if a job is running), cap `discover.extra`, and add per-IP rate limiting (e.g. slowapi). *(2 days)*
5. **Honesty pass on ML labels (E7, quick part).** Rename `opportunity_probability` → `opportunity_index` and `unusual_setup_score` → `relative_anomaly` (or hide them) until calibrated. No "probability"/"AI confidence" language that implies rigor that isn't there yet. *(half day)*

**Exit criteria:** no signal in the app traces to a fabricated mapping; adding a positive factor can never lower the score; a single user can't DoS the server; the public deploy refuses unauthenticated writes.

### Phase 1 — Foundation (make change safe) · ~2–4 weeks

*Goal: you can refactor the engine without fear, and it stays up.*

1. **CI + quality gates.** `.github/workflows/ci.yml`: run `pytest`, `ruff` (lint+format), `mypy`, and a frontend `eslint` + `vite build` on every PR. Gate `autoDeploy` behind green CI. Add `pyproject.toml` config. *(2 days)*
2. **Pin everything.** `==` versions + a compiled lockfile (`uv pip compile` / `pip-compile`); pin yfinance tightly; add `.python-version`. Add a `.dockerignore` and a non-root `USER` in the Dockerfile. *(1 day)*
3. **Test the engine (the value).** Golden-master tests for `indicators.py` (deterministic series → known RSI/MACD/ADX values), `analyze_symbol` (fixture OHLCV+info → asserted factor hits and score ranges), `scoring.py` (monotonicity, no-negative-contribution, saturation behavior). Add a `conftest.py` with a tmp-DB autouse fixture; standardize on pytest + `pytest-asyncio`. *(3–4 days)*
4. **SQLite hardening.** Centralize connection creation; set `journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL` on every connection; `VACUUM` weekly (or `auto_vacuum=INCREMENTAL`) not every 12h; `executemany` for snapshot batches. Add `PRAGMA user_version` + an ordered migration list. *(2 days)*
5. **Async hygiene.** Wrap all blocking `yf.*` in `asyncio.to_thread` (esp. `get_regime`, `/api/edge`); add exponential backoff + jitter; distinguish HTTP 429 from "no data" to stop false quarantines; cache `get_regime` ~5 min. Make `/api/health` a cheap liveness probe. Bound `state.jobs`/`state.symbols` (LRU/TTL). *(2 days)*
6. **Fix indicator math (E4) + lookahead contract (E8).** Wilder RSI/ADX with correct warm-up; require ≥60 bars for MACD; document and enforce "completed daily bars" (or slice `hist[index <= as_of]`); compute 52w range from `hist`, not `info`. Re-tune thresholds against the corrected indicators. *(2–3 days, behind the new tests)*

**Exit criteria:** green CI gates every deploy; engine has golden-master coverage; no `database is locked` under load; indicators match a reference (e.g. TA-Lib) within tolerance.

### Phase 2 — Prove the edge (turn "140 factors" into a measured model) · ~4–6 weeks · 🌟 the differentiator

*Goal: the score is calibrated and the app shows its own track record. This is the moat.*

1. **De-correlate the factors (E6).** Group correlated factors into families (MA-proximity, oversold-oscillators, volume-confirmation, insider-paths) and take a max / diminishing-return within each family before summing. Recompute "factors hit / total" so *missing data* (`na`) is distinct from *tested-and-failed* (`fail`) (`db.py:263-267`). *(3 days)*
2. **Bounded, monotonic score (E5).** Replace the clip-saturated linear sum with a bounded transform (logistic of the weighted sum) so ordering is preserved across the whole 0–100 range and a single S+ hit can't saturate it. *(2 days)*
3. **The self-validating flywheel (already 80% built — wire it up):**
   - Backend: cache forward-return outcomes in the DB instead of recomputing live in `recent_strong_snapshots_with_outcomes` (move yfinance off the request path); add per-factor empirical hit-rate (avg forward return when factor present vs absent).
   - Frontend: build the **Backtest/Edge view** that the `/api/edge` data already supports — score-bucket hit-rates, per-factor win-rates, equity curve of "would-have-bought" signals. *(1–1.5 weeks)*
4. **Calibrate weights from outcomes.** Replace hand-tuned weights in `factor_weights.py` (move to config) with weights informed by the empirical per-factor edge from #3. Show "calibrated from N snapshots over D days" in the UI. *(1 week)*
5. **Real smart-money data (replaces the deleted E1 aliases).** Route the insider loop through the *real* `event_crawler` Form-4 parser (delete the stub `insider_crawler.py`); add 13F-HR parsing for large managers; add a sourced India FII/promoter feed. Every smart-money badge links to its source filing/article. *(1–1.5 weeks)*
6. **Data-source abstraction.** Put yfinance behind a `PriceProvider` interface so a paid feed (Polygon/Finnhub/official NSE) can slot in; cache aggressively; add provider-health metrics. Fix news dedup (normalized-title hash), prune the static universe to a curated valid core + log every scrape fallback. *(1 week)*

**Exit criteria:** the app displays its own hit-rate by score bucket; weights are calibrated from data, not vibes; every smart-money signal is attributable to a real source.

### Phase 3 — World-class terminal UX · ~3–5 weeks (parallelizable with Phase 2)

1. **Performance:** `createSelector` memoized hot-pool shared across all consumers; `useMemo` on filter/sort; `React.memo` rows + sparklines; virtualize the table (`react-window`). Apply the existing flash-on-tick animations. *(1 week)*
2. **A11y:** Escape/scroll-lock/focus-trap on modals; keyboard-operable rows; `aria-label`s; fix light-theme contrast (theme tokens, not inline hex); `aria-live` for the intel feed. *(3–4 days)*
3. **Polish:** initial-load skeleton + snapshot hydration; wire the `toast` for mutation success/failure (kill silent `.catch`/`window.alert`); make the bell open an alerts panel; WS backoff + liveness; persist UI state to URL/localStorage; proper number formatting. *(1 week)*
4. **The terminal feel:** real candlestick charts (period/intraday toggle, volume, overlays) replacing sparklines on the detail panel; Cmd-K command palette; density controls. *(1.5–2 weeks)*
5. **Build hygiene:** decide the `frontend/` story (gitignore + build in CI/Docker, *or* a documented release step — never hand-edit minified bundles); `manualChunks` vendor split; add ErrorBoundary. *(2 days)*

### Phase 4 — Moat & scale · ongoing

- **Multi-user:** real auth (the spoofable bypass becomes proper sessions/JWT), server-persisted watchlists/portfolios/alert-rules per user (the DB tables largely exist).
- **Alerts engine:** persistent server-side rules ("buy_score>70 AND has_whale AND earnings<7d") → email/push/webhook; the snapshot fields already support this.
- **Regime awareness:** detect bull/bear/high-vol from breadth + indices; condition factor weights on regime (e.g. lower extension penalty in strong tape).
- **Observability:** structured logs + rotation, Sentry, a `/metrics` endpoint (the `state.stats` counters are already there), disk-full alerting.
- **Horizontal scale:** Redis for shared state + multi-worker; Postgres/Timescale if SQLite write contention becomes the ceiling.

---

## 6. The flywheel that makes it world-class

The single highest-leverage idea, because the raw material already exists:

```
scan snapshots ─► forward-return outcomes ─► per-factor & per-bucket hit-rates
      ▲                                                   │
      │                                                   ▼
  live scoring ◄── calibrated weights ◄── "which factors actually predicted returns?"
```

No competitor in the US+India retail scanner space shows users "here is my own measured hit-rate, and here's how I re-weighted myself because of it." That transparency — *the scanner that grades itself in public* — is the brand. Phase 2 builds it; everything else makes it usable.

---

## 7. Quick wins (this week, high value / low effort)

1. Delete the fabricated aliases (`universe.py:421-423`). **(hours)**
2. Fix `forwarded_allow_ips` + require a write key. **(hours)**
3. Single-flight guard + rate limit on the two DoS endpoints. **(half day)**
4. SQLite WAL + `busy_timeout` (one helper, applied everywhere). **(half day)**
5. `.dockerignore` + non-root Docker user. **(hours)**
6. Memoize the hot-pool selector (one `createSelector`, reused 4×) — instantly smoother UI. **(half day)**
7. Rename the mislabeled ML "probability" fields. **(hours)**
8. Minimal CI (`pytest` + `ruff`) on PRs. **(half day)**

These 8 remove the most dangerous trust/security issues and the worst UX jank in ~3 days.

---

## 8. Success metrics (definition of done for "world-class")

| Dimension | Today | World-class target |
|-----------|-------|--------------------|
| Fabricated/unsourced signals | present (E1) | **zero**; 100% of smart-money signals link to a source |
| Score calibration | none | published hit-rate monotonic in score bucket, shown in-app |
| Engine test coverage | 0% | ≥80% on `engine/`, golden-master locked |
| CI gate | none | required green check before deploy |
| Security | open + spoofable | auth' writes, rate-limited, no spoof, non-root |
| `database is locked` errors | likely under load | zero (WAL + busy_timeout) |
| UI re-render on WS tick | full 220-row repaint ×4 | memoized, virtualized, <16ms frame |
| A11y | keyboard-unusable tables/modals | WCAG AA, full keyboard nav |
| Reproducible build | `>=`, no lock | pinned + lockfile, deterministic |
| Data source | single unofficial (yfinance) | abstracted, cached, with paid fallback path |

---

## 9. Honest caveats

- **The free-data ceiling is real.** yfinance/RSS will never be a sub-second feed; "world-class data" eventually needs a paid provider. The architecture work in Phase 2 (`PriceProvider`) is what makes that a config change, not a rewrite.
- **Calibration needs history.** The backtest loop is only as good as the snapshot depth; retention is currently 3 days. Lengthen retention (cheaply) before trusting calibration, and label early calibration as preliminary.
- **Two-market scope doubles the data-quality burden.** India coverage is a differentiator *and* the most fragile part (NSE scraping, fewer reliable feeds). Treat India data quality as a first-class workstream, not an afterthought.
- **This is not financial advice and must keep saying so** — but "not advice" is not a license to show fabricated signals. Phase 0 is about earning the right to make the disclaimer honest.

---

### One-line summary

Market Pulse already has the *architecture* of a world-class US+India smart-money scanner; to actually become one it must, in order, **stop emitting false/incorrect signals (Phase 0)**, **make change safe (Phase 1)**, **prove its edge with a calibrated, self-validating engine (Phase 2 — the moat)**, then **make it feel like a real terminal (Phase 3)** and **scale to many users (Phase 4)**. Trust first, polish last.
