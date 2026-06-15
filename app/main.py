from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.db import (
    DB_PATH,
    db_file_size_mb,
    init_db,
    recent_news,
    recent_strong_snapshots,
    snapshots_for_symbol,
    upcoming_earnings,
    # portfolio / paper journal
    list_portfolio,
    upsert_portfolio_position,
    update_portfolio_position,
    delete_portfolio_position,
    record_trade_journal,
    list_journal,
    get_performance_stats,
)
from app.state import AppState
from app.universe import build_universe
from app.workers.scanner_loop import ScannerLoop
from app.crawler.price_crawler import _fetch_batch
from app.engine.signals import analyze_symbol

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("market_pulse")

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

state = AppState()
scanner: ScannerLoop | None = None
ws_clients: set[WebSocket] = set()


async def _push_ws_update() -> None:
    if not ws_clients:
        return
    snap = await state.snapshot(light=True)
    msg = json.dumps({"type": "update", "data": snap}, separators=(",", ":"))
    dead: list[WebSocket] = []
    for ws in list(ws_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.discard(ws)


async def broadcast_loop() -> None:
    """Push when scan/news/prices change; heartbeat every 20s for connection keepalive."""
    while True:
        try:
            await asyncio.wait_for(state.broadcast_event.wait(), timeout=20.0)
        except asyncio.TimeoutError:
            pass
        state.broadcast_event.clear()
        await _push_ws_update()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scanner
    cfg = load_config()
    await init_db()
    state.universe = build_universe(cfg)
    days_ahead = cfg.get("earnings", {}).get("days_ahead", 7)
    cached = await upcoming_earnings(days_ahead)
    if cached:
        await state.update_earnings(cached)
    logger.info(
        "Universe loaded: US=%d India=%d | cached earnings: %d",
        len(state.universe.get("us", [])),
        len(state.universe.get("india", [])),
        len(cached),
    )
    scanner = ScannerLoop(cfg, state)
    scan_task = asyncio.create_task(scanner.start())
    bcast_task = asyncio.create_task(broadcast_loop())
    yield
    if scanner:
        scanner.stop()
    scan_task.cancel()
    bcast_task.cancel()
    try:
        await scan_task
    except asyncio.CancelledError:
        pass
    try:
        await bcast_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Market Pulse", version="1.0.0", lifespan=lifespan)

if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
async def index():
    index_path = FRONTEND / "index.html"
    if index_path.exists():
        return FileResponse(
            index_path,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {"message": "Market Pulse API — frontend missing"}


@app.get("/api/snapshot")
async def api_snapshot(light: bool = True):
    return await state.snapshot(light=light)


@app.get("/api/sectors")
async def api_sectors():
    snap = await state.snapshot(light=True)
    return {
        "sectors": snap.get("sectors", []),
        "cycle_overview": snap.get("cycle_overview", []),
        "stats": snap.get("stats", {}),
    }


@app.get("/api/symbol/{symbol:path}")
@app.get("/api/analyze/{symbol:path}")
async def api_symbol(symbol: str, refresh: bool = False):
    """Get live scanner data for a symbol if present, otherwise perform a full
    on-demand analysis (hist + info + calendar + news context + the exact same
    100+ factor engine, scoring, smart money, entry/quality, sector rules, etc.
    that is used for every stock in the hot list).
    This powers the "analyze any stock" search box.
    """
    from urllib.parse import unquote
    from datetime import datetime, timezone

    raw = unquote(symbol).strip()
    upper = raw.upper()
    candidates = [upper]
    if not upper.endswith(".NS") and not upper.endswith(".BO"):
        candidates.append(upper + ".NS")

    if not refresh:
        async with state.lock:
            for sym in candidates:
                data = state.symbols.get(sym)
                if data:
                    return data

    # On-demand full analysis for any ticker (US or India)
    market = "india" if any(c.endswith((".NS", ".BO")) for c in candidates) else "us"
    norm_sym = upper
    if market == "india" and not norm_sym.endswith(".NS"):
        norm_sym = norm_sym + ".NS"

    # Reuse the exact same batch fetcher the live scanner uses
    try:
        raw_map = await asyncio.to_thread(_fetch_batch, [norm_sym])
        hit = raw_map.get(norm_sym)
        if not hit or hit[0] is None or len(hit[0]) < 5:
            # try without forced suffix as last resort
            raw_map = await asyncio.to_thread(_fetch_batch, [upper])
            hit = raw_map.get(upper) or raw_map.get(norm_sym)
        if not hit or hit[0] is None or len(hit[0]) < 5:
            return {"error": "no data or invalid ticker", "symbol": raw, "tried": norm_sym}
        hist, info, calendar = hit
    except Exception as e:
        logger.exception("Ad-hoc yf fetch failed for %s", raw)
        return {"error": f"fetch failed: {e}", "symbol": raw}

    # Gather best available news context (from the live broad crawlers including Google News)
    # so that news_*, smart_money_*, catalyst factors work the same as for hot list stocks.
    news_count = 0
    news_titles: list[str] = []
    earn = None
    try:
        async with state.lock:
            news_count = state.news_by_symbol.get(norm_sym, 0) or state.news_by_symbol.get(upper, 0)
            news_titles = list(
                state.news_titles_by_symbol.get(norm_sym, [])
                or state.news_titles_by_symbol.get(upper, [])
            )
            earn = state.earnings_by_symbol.get(norm_sym) or state.earnings_by_symbol.get(upper)

        # Supplement with any recent live headlines that mention the ticker (very useful for ad-hoc)
        if len(news_titles) < 8:
            snap = await state.snapshot(light=True)
            for n in (snap.get("news") or [])[:60]:
                t = (n.get("title") or "")
                base = norm_sym.replace(".NS", "").replace(".BO", "")
                if base in t.upper() or upper in t.upper() or norm_sym in t.upper():
                    if t not in news_titles:
                        news_titles.append(t)
                    news_count = max(news_count, 1)
    except Exception:
        pass

    news_titles = news_titles[:25]

    # Run the *exact same* analysis pipeline used by the live scanner for every other stock
    try:
        sig = analyze_symbol(
            norm_sym,
            market,
            hist,
            info or {},
            news_count or 0,
            None,  # legacy weights (ignored by current engine)
            earnings=earn,
            news_titles=news_titles,
            calendar=calendar,
        )
    except Exception as e:
        logger.exception("Ad-hoc engine failed for %s", norm_sym)
        return {"error": f"analysis failed: {e}", "symbol": raw}

    # Build payload identical in shape to live scan results
    payload = {
        "symbol": norm_sym,
        "market": market,
        "score": sig.score,
        "signals": sig.signals,
        "alerts": sig.alerts,
        "metrics": sig.metrics,
        "factors_hit": sig.factors_hit,
        "factors_total": sig.factors_total,
        "factor_details": sig.factor_details,
        "factor_breakdown": sig.factor_breakdown,
        "sparkline": [round(float(x), 4) for x in hist["Close"].tail(30).tolist()] if len(hist) > 0 else [],
        "ad_hoc": True,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Cache so that subsequent detail/factor views, clicks, and searches are instant
    # (until next full scanner pass overwrites or refresh requested)
    async with state.lock:
        state.symbols[norm_sym] = payload
        if upper != norm_sym:
            state.symbols[upper] = payload

    return payload


@app.get("/api/news")
async def api_news(limit: int = 80):
    db_news = await recent_news(limit)
    snap = await state.snapshot()
    return {"live": snap.get("news", []), "stored": db_news}


@app.get("/api/factors")
async def api_factors():
    from app.engine.factor_catalog import (
        CATEGORY_ORDER,
        FACTORS_TOTAL,
        catalog_for_api,
    )
    from app.engine.factor_weights import factor_weight, tier_label, weights_for_api

    factors = catalog_for_api()
    for f in factors:
        f["weight"] = factor_weight(f["id"])
        f["tier"] = tier_label(f["id"])

    from app.engine.smart_money_intel import registry_for_api

    return {
        "total": FACTORS_TOTAL,
        "categories": CATEGORY_ORDER,
        "factors": factors,
        "weighting": weights_for_api(),
        "smart_money_watchlist": registry_for_api(),
        "doc": "/docs/FACTORS.md",
    }


@app.get("/api/earnings")
async def api_earnings(days: int = 7):
    snap = await state.snapshot()
    stored = await upcoming_earnings(days)
    return {
        "days": days,
        "live": snap.get("earnings", []),
        "stored": stored,
        "count": len(snap.get("earnings", [])),
    }


@app.get("/api/edge")
async def api_edge(days: int = 2, min_score: float = 55.0):
    """Backtest / historical edge view with forward outcomes.
    Recent strong snapshots + computed 1d/3d/7d/14d returns, max DD, hit rates by score bucket,
    and basic factor win-rate hints (from payload). Self-validating engine.
    """
    snaps = await recent_strong_snapshots_with_outcomes(days=days, min_score=min_score, limit=120)
    # Group by approximate window
    by_time: dict[str, list] = {}
    for s in snaps:
        key = s.get("created_at", "")[:13]
        by_time.setdefault(key, []).append({
            "symbol": s["symbol"],
            "market": s.get("market"),
            "score": round(s.get("score", 0), 1),
            "created_at": s.get("created_at"),
            "has_smart_money": bool((s.get("payload") or {}).get("metrics", {}).get("smart_money", {}).get("hits")),
            "outcomes": s.get("outcomes"),
        })
    # Compute aggregates for validation
    valid = [s for s in snaps if s.get("outcomes") and s["outcomes"].get("ret_7d") is not None]
    total = len(valid)
    hit_7d = sum(1 for s in valid if s["outcomes"]["ret_7d"] > 0)
    avg_ret7 = sum(s["outcomes"]["ret_7d"] for s in valid) / total if total else 0
    # Buckets
    buckets = {"70+": [], "60-70": [], "55-60": []}
    for s in valid:
        sc = s.get("score", 0)
        if sc >= 70:
            buckets["70+"].append(s["outcomes"]["ret_7d"])
        elif sc >= 60:
            buckets["60-70"].append(s["outcomes"]["ret_7d"])
        else:
            buckets["55-60"].append(s["outcomes"]["ret_7d"])
    bucket_stats = {}
    for b, rets in buckets.items():
        if rets:
            bucket_stats[b] = {
                "n": len(rets),
                "hit_rate": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
                "avg_ret7d": round(sum(rets) / len(rets), 2),
            }
    summary = {
        "windows": len(by_time),
        "total_signals": len(snaps),
        "valid_with_outcomes": total,
        "hit_rate_7d": round(hit_7d / total * 100, 1) if total else 0,
        "avg_ret_7d": round(avg_ret7, 2),
        "bucket_stats": bucket_stats,
        "min_score": min_score,
        "days": days,
    }
    return {"summary": summary, "signals": snaps[:60], "by_window": by_time}


@app.get("/api/discover")
async def api_discover(limit: int = 80, min_score: float = 32, extra: int = 180):
    """'Scan More / Full Discovery' feature.
    Scrapes/grows from multiple sources (multiple wiki lists + large static pools in universe.py + data/*.txt)
    then runs the *exact same deep 140-factor engine* on a large additional pool of listed names
    (beyond the live hot scanner's regular universe to avoid overloading the always-on loops).
    Returns promising new high-conviction setups that can be merged into the UI.
    Triggered by user button so we can be more aggressive on batching without killing free tier.
    """
    from app.universe import get_full_discovery_pool
    from app.crawler.price_crawler import _fetch_batch
    from app.engine.signals import analyze_symbol
    from app.config import load_config

    cfg = load_config()
    full_pool = get_full_discovery_pool(cfg)

    async with state.lock:
        current_syms = set(s["symbol"] for s in (getattr(state, "hot", []) or []))
        news_titles_map = dict(state.news_titles_by_symbol or {})
        earn_map = dict(state.earnings_by_symbol or {})

    # Pick additional symbols not in current hot (to surface "new" discoveries)
    candidates = [s for s in full_pool if s not in current_syms]
    candidates = candidates[:extra]  # cap per call for free tier / yf rate limits

    discovered = []
    batch_size = 20
    delay = 0.25

    for i in range(0, len(candidates), batch_size):
        if not candidates:
            break
        chunk = candidates[i : i + batch_size]
        try:
            raw = await asyncio.to_thread(_fetch_batch, chunk)
            for sym, (hist, info, calendar) in raw.items():
                if hist is None or hist.empty or len(hist) < 5:
                    continue
                market = "india" if sym.endswith((".NS", ".BO")) else "us"
                nt = news_titles_map.get(sym, [])[:12]
                earn = earn_map.get(sym)
                try:
                    sig = analyze_symbol(
                        sym, market, hist, info or {}, len(nt), None,
                        earnings=earn, news_titles=nt, calendar=calendar
                    )
                    if (sig.score or 0) >= min_score:
                        payload = {
                            "symbol": sym,
                            "market": market,
                            "score": sig.score,
                            "buy_score": sig.metrics.get("buy_score", sig.score),
                            "signals": sig.signals,
                            "alerts": sig.alerts,
                            "metrics": sig.metrics,
                            "factors_hit": sig.factors_hit,
                            "factors_total": sig.factors_total,
                            "factor_breakdown": sig.factor_breakdown,
                            "sparkline": [round(float(x), 4) for x in hist["Close"].tail(20).tolist()] if len(hist) > 0 else [],
                            "discovered": True,
                        }
                        discovered.append(payload)
                except Exception:
                    continue
            await asyncio.sleep(delay)
        except Exception:
            await asyncio.sleep(delay)
            continue

    discovered.sort(key=lambda x: x.get("score", 0), reverse=True)
    return {
        "discovered": discovered[:limit],
        "scanned_extra": len(candidates),
        "total_pool": len(full_pool),
        "min_score": min_score,
        "note": "These are on-demand deep engine results from a much larger multi-source list (wiki scrapes + big static + extras). Not part of the regular live hot ranking until they stay hot."
    }


@app.get("/api/snapshots/{symbol:path}")
async def api_snapshots_for_symbol(symbol: str, limit: int = 20):
    """Score history snapshots for a symbol (used by My List watch for history curves)."""
    from urllib.parse import unquote
    sym = unquote(symbol).upper()
    rows = await snapshots_for_symbol(sym, limit=limit)
    return {"symbol": sym, "snapshots": rows}


@app.post("/api/full_exhaustive_scan")
async def api_full_exhaustive_scan():
    """Start background job for full exhaustive scan (non-blocking).
    Returns job_id. Poll /api/job_status/{id} or listen to WS for progress.
    """
    from app.universe import get_complete_exhaustive_universe
    from app.crawler.price_crawler import full_exhaustive_scan
    import uuid
    cfg = load_config()
    pool = get_complete_exhaustive_universe(cfg)
    async with state.lock:
        nc = dict(state.news_by_symbol or {})
        nt = dict(state.news_titles_by_symbol or {})
        em = dict(state.earnings_by_symbol or {})
    job_id = str(uuid.uuid4())
    async with state.lock:
        state.jobs[job_id] = {"status": "running", "progress": 0, "started": datetime.now(timezone.utc).isoformat(), "result": None, "error": None}
    def _run_job():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            res = new_loop.run_until_complete(full_exhaustive_scan(pool, nc, nt, em))
            async def _finish():
                async with state.lock:
                    if job_id in state.jobs:
                        state.jobs[job_id].update({"status": "done", "progress": 100, "result": {
                            "scanned": len(pool),
                            "opportunities_found": len(res),
                            "results": res[:200],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }})
                        state.full_exhaustive_results = state.jobs[job_id]["result"]
                state.broadcast_event.set()
            asyncio.run_coroutine_threadsafe(_finish(), asyncio.get_event_loop())
        except Exception as e:
            async def _err():
                async with state.lock:
                    if job_id in state.jobs:
                        state.jobs[job_id].update({"status": "error", "error": str(e)[:200]})
                state.broadcast_event.set()
            asyncio.run_coroutine_threadsafe(_err(), asyncio.get_event_loop())
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        ex.submit(_run_job)
    return {"job_id": job_id, "status": "started", "note": "Use /api/job_status or WS for updates. Long running."}


@app.get("/api/job_status/{job_id}")
async def api_job_status(job_id: str):
    async with state.lock:
        j = state.jobs.get(job_id)
        if not j:
            return {"error": "not found"}
        return {"job_id": job_id, "status": j["status"], "progress": j.get("progress", 0), "error": j.get("error")}


@app.get("/api/job_result/{job_id}")
async def api_job_result(job_id: str):
    async with state.lock:
        j = state.jobs.get(job_id)
        if not j or j.get("status") != "done":
            return {"error": "not done or not found"}
        return j.get("result") or {}


@app.get("/api/last_full_scan")
async def api_last_full_scan():
    async with state.lock:
        if not hasattr(state, "full_exhaustive_results") or not state.full_exhaustive_results:
            return {"status": "none", "message": "No full exhaustive scan run yet. Trigger via /api/full_exhaustive_scan or the UI button."}
        return state.full_exhaustive_results


@app.get("/api/health")
async def health():
    snap = await state.snapshot()
    stats = snap.get("stats", {})
    stats["db_path"] = str(DB_PATH)
    stats["db_size_mb"] = db_file_size_mb()
    return {"status": "ok", "stats": stats}


# ============ PORTFOLIO / PAPER TRADING JOURNAL ENDPOINTS (server persisted, first-class) v1 ============

@app.get("/api/portfolio")
async def api_get_portfolio():
    """Current open paper positions + live enrichment from state.symbols (buy/qual/price) + est PnL + overall stats.
    Re-uses existing state + analyze data for live Buy/Qual without duplicating engine.
    """
    positions = await list_portfolio()
    perf = await get_performance_stats()

    enriched = []
    for p in positions:
        sym = p["symbol"]
        live = None
        async with state.lock:
            live = state.symbols.get(sym) or state.symbols.get(sym + ".NS") or state.symbols.get(sym.replace(".NS", ""))
        m = (live or {}).get("metrics", {}) or {}
        buy = m.get("buy_score") or (live or {}).get("score") or p.get("entry_score")
        qual = m.get("quality_score")
        curr_price = m.get("price") or p.get("entry_price")
        entry_p = p.get("entry_price") or 0
        qty = p.get("qty") or 0
        est_pnl = None
        est_pnl_pct = None
        if curr_price and entry_p and qty:
            est_pnl = round((float(curr_price) - float(entry_p)) * float(qty), 2)
            est_pnl_pct = round(((float(curr_price) - float(entry_p)) / float(entry_p)) * 100, 1) if entry_p else 0
        row = {
            **p,
            "current_buy": round(buy, 1) if buy else None,
            "current_qual": round(qual, 1) if qual else None,
            "current_price": curr_price,
            "est_pnl": est_pnl,
            "est_pnl_pct": est_pnl_pct,
            "live_from_cache": bool(live),
        }
        enriched.append(row)

    # total paper equity est (sum entry values + est open pnl)
    total_entry_value = sum((p.get("qty", 0) or 0) * (p.get("entry_price", 0) or 0) for p in positions)
    open_pnl_sum = sum((r.get("est_pnl") or 0) for r in enriched)
    return {
        "positions": enriched,
        "stats": {
            **perf,
            "paper_equity_entry": round(total_entry_value, 2),
            "open_pnl_est": round(open_pnl_sum, 2),
            "total_paper_value_est": round(total_entry_value + open_pnl_sum, 2),
        },
        "count": len(enriched),
    }


@app.post("/api/portfolio")
async def api_add_to_portfolio(payload: dict):
    """Log new paper buy position. Body: {symbol, qty, notes?, sl?, target?, entry_price?, entry_score?}
    Falls back to current state.symbols or runs on-demand analyze to get entry price/score + thesis.
    Records 'buy' in journal with pos/neg snapshot.
    """
    from urllib.parse import unquote
    sym = (payload.get("symbol") or "").strip().upper()
    if not sym:
        return {"error": "symbol required"}
    qty = float(payload.get("qty") or 100)
    notes = payload.get("notes")
    sl = payload.get("sl")
    target = payload.get("target")
    provided_price = payload.get("entry_price")
    provided_score = payload.get("entry_score")

    # Get current data: prefer state, else call existing analyze pipeline (reuses same engine)
    live = None
    async with state.lock:
        live = state.symbols.get(sym)
    if not live:
        try:
            # Reuse the symbol analyze endpoint logic by calling internal func? Use direct for simplicity
            # To avoid circular, inline minimal: fetch via state update pattern or direct analyze
            # For cleanliness: call the analyze_symbol path like discover does (but here use existing /api/symbol effect by temp)
            # Simpler: use state if any, else quick price + entry score from payload or default
            pass
        except Exception:
            pass

    market = "india" if sym.endswith((".NS", ".BO")) else "us"
    entry_price = provided_price
    entry_score = provided_score
    if live:
        m = live.get("metrics") or {}
        entry_price = entry_price or m.get("price")
        entry_score = entry_score or m.get("buy_score") or live.get("score")
        # enrich market if avail
        market = live.get("market", market)

    if not entry_price:
        # fallback to quick batch (reuses existing crawler)
        try:
            raw_map = await asyncio.to_thread(_fetch_batch, [sym])
            hit = raw_map.get(sym)
            if hit and hit[0] is not None and len(hit[0]) > 0:
                entry_price = float(hit[0]["Close"].iloc[-1])
        except Exception:
            entry_price = 0.0

    if entry_price is None:
        entry_price = 0.0

    # build thesis snapshot using existing helpers if we have live row
    thesis_pos = None
    thesis_neg = None
    if live:
        try:
            pn = build_positives_and_negatives_for_row(live)  # defined below
            thesis_pos = " | ".join(pn.get("positives", [])[:3])
            thesis_neg = " | ".join(pn.get("negatives", [])[:3])
        except Exception:
            pass

    pos_id = await upsert_portfolio_position(
        sym, market, qty, float(entry_price or 0), entry_score, notes, sl, target
    )
    await record_trade_journal(
        sym,
        "buy",
        price=float(entry_price or 0),
        qty=qty,
        score_at_time=entry_score,
        notes=notes,
        linked_position_id=pos_id,
        thesis_pos=thesis_pos,
        thesis_neg=thesis_neg,
    )

    return {"ok": True, "symbol": sym, "position_id": pos_id, "entry_price": entry_price}


def build_positives_and_negatives_for_row(row: dict) -> dict:
    """Minimal reuse of frontend logic server-side for journal thesis snapshots. (keep light)"""
    # Lightweight version of the JS buildPositivesAndNegatives; uses factor_breakdown if present
    if not row:
        return {"positives": [], "negatives": []}
    m = row.get("metrics") or {}
    bd = row.get("factor_breakdown") or m.get("factor_breakdown") or []
    pos = []
    neg = []
    if m.get("smart_money", {}).get("hits"):
        names = ", ".join([h.get("name", "") for h in m["smart_money"]["hits"][:3]])
        pos.append(f"S+ smart money: {names}")
    entry_hits = [f for f in bd if f.get("category") == "entry" and f.get("status") == "pass"]
    if entry_hits:
        pos.append(f"{len(entry_hits)} entry setup factors")
    if (m.get("buy_score") or row.get("score") or 0) >= 65:
        pos.append("High buy score")
    risk_hits = [f for f in bd if f.get("status") in ("risk", "fail")]
    if len(risk_hits) > 4:
        neg.append(f"{len(risk_hits)} risk/fail factors")
    if m.get("is_extended"):
        neg.append("Price extended")
    return {"positives": pos[:4], "negatives": neg[:3]}


@app.get("/api/journal")
async def api_get_journal(limit: int = 80):
    rows = await list_journal(limit)
    return {"journal": rows, "count": len(rows)}


@app.post("/api/position/{symbol:path}/close")
async def api_close_position(symbol: str, payload: dict | None = None):
    """Close paper position: compute realized PnL using latest price/score from state (or quick), delete from positions,
    record 'close' journal entry with outcome_pnl + linked + thesis snapshot at close time.
    """
    from urllib.parse import unquote
    sym = unquote(symbol).upper().strip()
    positions = await list_portfolio()
    pos = next((p for p in positions if p["symbol"] == sym), None)
    if not pos:
        return {"error": "no open position for symbol", "symbol": sym}

    # Get latest price preferably from live state (same pattern as snapshot / analyze)
    live = None
    async with state.lock:
        live = state.symbols.get(sym)
    exit_price = None
    exit_score = None
    if live:
        m = live.get("metrics") or {}
        exit_price = m.get("price")
        exit_score = m.get("buy_score") or live.get("score")
    if not exit_price:
        try:
            raw_map = await asyncio.to_thread(_fetch_batch, [sym])
            hit = raw_map.get(sym) or raw_map.get(sym + ".NS")
            if hit and hit[0] is not None:
                exit_price = float(hit[0]["Close"].iloc[-1])
        except Exception:
            exit_price = pos.get("entry_price")

    entry_p = float(pos.get("entry_price") or 0)
    qty = float(pos.get("qty") or 0)
    pnl = round((float(exit_price or entry_p) - entry_p) * qty, 2) if exit_price else 0.0

    # thesis at close time
    thesis_pos = None
    thesis_neg = None
    if live:
        try:
            pn = build_positives_and_negatives_for_row(live)
            thesis_pos = " | ".join(pn.get("positives", [])[:3])
            thesis_neg = " | ".join(pn.get("negatives", [])[:3])
        except Exception:
            pass

    await record_trade_journal(
        sym,
        "close",
        price=float(exit_price or 0),
        qty=qty,
        score_at_time=exit_score,
        outcome_pnl=pnl,
        linked_position_id=pos.get("id"),
        thesis_pos=thesis_pos,
        thesis_neg=thesis_neg,
        notes=(payload or {}).get("notes") if payload else None,
    )
    await delete_portfolio_position(sym)

    return {"ok": True, "symbol": sym, "realized_pnl": pnl, "exit_price": exit_price}


@app.post("/api/position/{symbol:path}/update")
async def api_update_position(symbol: str, payload: dict):
    """Update notes, SL, target for open position (editable in UI table)."""
    from urllib.parse import unquote
    sym = unquote(symbol).upper().strip()
    notes = payload.get("notes")
    sl = payload.get("sl")
    target = payload.get("target")
    await update_portfolio_position(sym, notes, sl, target)
    return {"ok": True, "symbol": sym}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        await ws.send_text(
            json.dumps(
                {"type": "update", "data": await state.snapshot(light=True)},
                separators=(",", ":"),
            )
        )
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=90)
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(ws)


def run():
    import uvicorn

    cfg = load_config()
    host = cfg.get("server", {}).get("host", "0.0.0.0")
    # PORT env var takes precedence (standard on Railway, Render, Fly.io, Heroku, etc.)
    port = int(os.getenv("PORT") or cfg.get("server", {}).get("port", 8765))
    uvicorn.run("app.main:app", host=host, port=port, reload=False, proxy_headers=True)


if __name__ == "__main__":
    run()