from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.db import (
    DB_PATH,
    add_alert_rule,
    add_to_watchlist,
    db_file_size_mb,
    delete_alert_rule,
    evaluate_rules_for_snapshot,
    get_or_create_default_rules,
    init_db,
    insert_alert,
    list_alert_rules,
    list_watchlist,
    recent_alerts,
    recent_market_events,
    recent_strong_snapshots,
    recent_strong_snapshots_with_outcomes,
    remove_from_watchlist,
    snapshots_for_symbol,
    upcoming_earnings,
    update_alert_rule_last_triggered,
)
from app.engine.candidate_scanner import build_event_candidates
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


async def _push_alert_event(alert_item: dict) -> None:
    """Dedicated immediate alert push for high-conviction / rule matches (rich text preserved)."""
    if not ws_clients:
        return
    payload = {
        "type": "alert",
        "alert": alert_item,
        "ts": alert_item.get("ts") or alert_item.get("triggered_at"),
    }
    msg = json.dumps(payload, separators=(",", ":"))
    dead: list[WebSocket] = []
    for ws in list(ws_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.discard(ws)


async def _refresh_state_watches_and_alerts() -> None:
    """Load persisted into state for snapshot + restart safety."""
    try:
        w = await list_watchlist()
        async with state.lock:
            state.watches = w
        al = await recent_alerts(limit=30)
        async with state.lock:
            state.recent_server_alerts = al
    except Exception:
        pass


async def _evaluate_and_fire_alerts(data_for_eval: dict | None = None, symbols_rows: list[dict] | None = None) -> list[dict]:
    """
    Run rule engine against current hot + investor_events (exact same smart_money + scoring data).
    For each triggered: insert to alerts+market_events, update rule last_triggered, push WS + update state.
    Auto-add high priority matches to watchlist (per spec).
    """
    try:
        trigs = await evaluate_rules_for_snapshot(data_for_eval, symbols_rows)
        fired = []
        for t in trigs:
            sym = t["symbol"]
            msg = t["message"]
            rid = t.get("rule_id")
            rtype = t.get("rule_type")
            bs = t.get("buy_score")
            det = t.get("details", {})
            # Persist
            aid = await insert_alert(
                symbol=sym,
                message=msg,
                rule_id=rid,
                rule_type=rtype,
                buy_score=bs,
                details=det,
            )
            if rid:
                await update_alert_rule_last_triggered(rid)  # need import? wait we'll add
            # Auto-add to watch if high conviction (investor or high score)
            if det.get("has_investor") or (bs and bs >= 65):
                try:
                    await add_to_watchlist(sym, notes="auto from alert rule")
                except Exception:
                    pass
            # Update in-memory recent
            alert_rec = {
                "id": aid,
                "symbol": sym,
                "rule_id": rid,
                "rule_type": rtype,
                "message": msg,
                "triggered_at": t.get("ts"),
                "buy_score": bs,
                "details": det,
            }
            async with state.lock:
                state.recent_server_alerts = [alert_rec] + [a for a in state.recent_server_alerts if a.get("symbol") != sym][:29]
                # also sync watches if auto-added
                if any(ww.get("symbol") == sym for ww in state.watches):
                    pass
                else:
                    state.watches = [{"symbol": sym, "added_at": t.get("ts"), "notes": "auto"}] + state.watches[:199]
            # Immediate WS alert (rich "🚨 Investor: ..." preserved in message)
            await _push_alert_event(alert_rec)
            fired.append(alert_rec)
        if fired:
            # Also cause full snapshot push
            state.broadcast_event.set()
        return fired
    except Exception as e:
        logger.warning("Alert rule eval failed: %s", e)
        return []


async def broadcast_loop() -> None:
    """Push when scan/news/prices change; heartbeat every 20s for connection keepalive.
    Also evaluate personalized alert rules here (on scan updates) against hot + investor_events.
    Fires server alerts (WS 'alert' + persisted + auto-watch for high-conviction exact investor moves).
    """
    while True:
        try:
            await asyncio.wait_for(state.broadcast_event.wait(), timeout=20.0)
        except asyncio.TimeoutError:
            pass
        state.broadcast_event.clear()
        # Refresh watches/alerts from DB for snapshot accuracy
        await _refresh_state_watches_and_alerts()
        # Evaluate rules on the fresh snapshot data (reuses exact analyze/smart_money/investor_events pipeline)
        try:
            snap = await state.snapshot(light=False)
            # Use full for earnings/investor, but slim hot is ok
            await _evaluate_and_fire_alerts(snap, list(snap.get("hot") or []))
        except Exception:
            pass
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
    stored_events = await recent_market_events(limit=250)
    if stored_events:
        await state.update_events(stored_events)
        await state.update_candidates(build_event_candidates(state.events_by_symbol, state.symbols))
    # Load server watchlists + alert rules + seed defaults + recent alerts (restart-safe, multi-device)
    await get_or_create_default_rules()
    await _refresh_state_watches_and_alerts()
    logger.info(
        "Universe loaded: US=%d India=%d | cached earnings: %d | cached events: %d | watches: %d | alert_rules: %d",
        len(state.universe.get("us", [])),
        len(state.universe.get("india", [])),
        len(cached),
        len(stored_events),
        len(state.watches),
        len(await list_alert_rules()),
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
    market_events: list[dict] = []
    earn = None
    try:
        async with state.lock:
            news_count = state.news_by_symbol.get(norm_sym, 0) or state.news_by_symbol.get(upper, 0)
            news_titles = list(
                state.news_titles_by_symbol.get(norm_sym, [])
                or state.news_titles_by_symbol.get(upper, [])
            )
            market_events = list(
                state.events_by_symbol.get(norm_sym, [])
                or state.events_by_symbol.get(upper, [])
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
            market_events=market_events,
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


@app.get("/api/events")
@app.get("/api/events/recent")
async def api_events(limit: int = 100, symbol: Optional[str] = None):
    safe_limit = max(1, min(limit, 500))
    sym = symbol.upper() if symbol else None
    stored = await recent_market_events(limit=safe_limit, symbol=sym)
    async with state.lock:
        if sym:
            live = list(state.events_by_symbol.get(sym, []))[:safe_limit]
        else:
            live = list(state.events[:safe_limit])
    return {
        "symbol": sym,
        "limit": safe_limit,
        "live": live,
        "stored": stored,
        "count": len(live),
    }


@app.get("/api/candidates")
async def api_candidates(limit: int = 120, refresh: bool = False):
    safe_limit = max(1, min(limit, 300))
    if refresh:
        async with state.lock:
            events_by_symbol = {
                sym: list(events)
                for sym, events in state.events_by_symbol.items()
            }
            symbols_cache = dict(state.symbols)
        await state.update_candidates(
            build_event_candidates(events_by_symbol, symbols_cache, limit=300)
        )
    async with state.lock:
        candidates = list(state.candidates[:safe_limit])
    return {
        "limit": safe_limit,
        "count": len(candidates),
        "candidates": candidates,
    }


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
        events_by_symbol = {
            sym: list(events)
            for sym, events in (state.events_by_symbol or {}).items()
        }

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
                        earnings=earn,
                        news_titles=nt,
                        market_events=events_by_symbol.get(sym, []),
                        calendar=calendar,
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
        events_by_symbol = {
            sym: list(events)
            for sym, events in (state.events_by_symbol or {}).items()
        }
    job_id = str(uuid.uuid4())
    async with state.lock:
        state.jobs[job_id] = {"status": "running", "progress": 0, "started": datetime.now(timezone.utc).isoformat(), "result": None, "error": None}

    async def _run_job():
        async with state.lock:
            if job_id in state.jobs:
                state.jobs[job_id]["progress"] = 5
        state.broadcast_event.set()

        def _blocking_scan():
            return asyncio.run(full_exhaustive_scan(pool, nc, nt, em, events_by_symbol))

        try:
            res = await asyncio.to_thread(_blocking_scan)
            async with state.lock:
                if job_id in state.jobs:
                    state.jobs[job_id].update({"status": "done", "progress": 100, "result": {
                        "scanned": len(pool),
                        "opportunities_found": len(res),
                        "results": res[:200],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }})
                    state.full_exhaustive_results = state.jobs[job_id]["result"]
        except Exception as e:
            async with state.lock:
                if job_id in state.jobs:
                    state.jobs[job_id].update({"status": "error", "error": str(e)[:200]})
        state.broadcast_event.set()

    asyncio.create_task(_run_job())
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


# ===================== Watchlist + Alert Rules CRUD (server-persisted) =====================

@app.get("/api/watchlist")
async def api_list_watchlist():
    items = await list_watchlist()
    async with state.lock:
        state.watches = items
    return {"watches": items, "count": len(items)}


@app.post("/api/watchlist")
async def api_add_watch(payload: dict):
    sym = (payload.get("symbol") or "").strip().upper()
    notes = payload.get("notes") or ""
    if not sym:
        return {"error": "symbol required"}
    ok = await add_to_watchlist(sym, notes)
    await _refresh_state_watches_and_alerts()
    state.broadcast_event.set()
    return {"ok": ok, "symbol": sym, "watches": await list_watchlist()}


@app.delete("/api/watchlist/{symbol:path}")
async def api_remove_watch(symbol: str):
    from urllib.parse import unquote
    sym = unquote(symbol).upper()
    await remove_from_watchlist(sym)
    await _refresh_state_watches_and_alerts()
    state.broadcast_event.set()
    return {"ok": True, "symbol": sym}


@app.get("/api/alert_rules")
async def api_list_alert_rules():
    rules = await list_alert_rules()
    return {"rules": rules, "count": len(rules)}


@app.post("/api/alert_rules")
async def api_add_alert_rule(payload: dict):
    rtype = payload.get("rule_type", "custom")
    cond = payload.get("condition") or payload.get("conditions") or {}
    enabled = payload.get("enabled", True)
    rid = await add_alert_rule(rtype, cond, bool(enabled))
    return {"id": rid, "rule_type": rtype, "condition": cond, "enabled": bool(enabled)}


@app.delete("/api/alert_rules/{rule_id}")
async def api_delete_alert_rule(rule_id: int):
    await delete_alert_rule(rule_id)
    return {"ok": True, "id": rule_id}


@app.post("/api/alert_rules/eval")
async def api_manual_eval_alerts():
    """Manual trigger for testing/eval against current state snapshot + hot + investor_events."""
    snap = await state.snapshot(light=False)
    fired = await _evaluate_and_fire_alerts(snap, snap.get("hot", []))
    return {"fired": len(fired), "alerts": fired}


@app.get("/api/alerts/recent")
async def api_recent_alerts(limit: int = 50):
    al = await recent_alerts(limit)
    async with state.lock:
        state.recent_server_alerts = al[:30]
    return {"alerts": al, "count": len(al)}


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
