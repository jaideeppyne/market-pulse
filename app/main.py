from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
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
    list_journal,
    list_portfolio,
    list_watchlist,
    remove_from_watchlist,
    recent_alerts,
    recent_market_events,
    recent_news,
    recent_strong_snapshots_with_outcomes,
    record_trade_journal,
    snapshots_for_symbol,
    upcoming_earnings,
    update_alert_rule_last_triggered,
    update_portfolio_position,
    upsert_portfolio_position,
    delete_portfolio_position,
    get_performance_stats,
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


@dataclass(frozen=True)
class ResolvedAnalyzeSymbol:
    raw: str
    normalized: str
    market: str
    candidates: list[str]


NAME_TO_TICKER = {
    "MICRON": "MU",
    "MICRON TECHNOLOGY": "MU",
    "MICRON TECH": "MU",
    "NVIDIA": "NVDA",
    "NVDA": "NVDA",
    "GOOGLE": "GOOGL",
    "GOOG": "GOOGL",
    "AMAZON": "AMZN",
    "META": "META",
    "FACEBOOK": "META",
    "RELIANCE": "RELIANCE.NS",
    "RELIANCE INDUSTRIES": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "TATA CONSULTANCY": "TCS.NS",
    "INFOSYS": "INFY.NS",
    "HDFC BANK": "HDFCBANK.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICI BANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "SBI": "SBIN.NS",
    "TATA MOTORS": "TATAMOTORS.NS",
    "ADANI": "ADANIENT.NS",
    "APPLE": "AAPL",
}


def _base_symbol(sym: str) -> str:
    s = str(sym or "").upper()
    for suffix in (".NS", ".BO", ".L"):
        if s.endswith(suffix):
            return s[: -len(suffix)]
    return s


def resolve_analyze_symbol(symbol: str) -> ResolvedAnalyzeSymbol:
    """Resolve search/analyze input without turning plain US tickers into .NS tickers."""
    from urllib.parse import unquote

    raw = unquote(symbol).strip()
    upper = raw.upper()
    resolved = NAME_TO_TICKER.get(upper, upper)
    if resolved == upper:
        for alias, tkr in NAME_TO_TICKER.items():
            if alias in upper or upper in alias:
                resolved = tkr
                break
    upper = resolved

    if upper.endswith((".NS", ".BO")):
        return ResolvedAnalyzeSymbol(raw=raw, normalized=upper, market="india", candidates=[upper])
    if upper.endswith(".L"):
        return ResolvedAnalyzeSymbol(raw=raw, normalized=upper, market="uk", candidates=[upper])

    universe = getattr(state, "universe", {}) or {}
    us_symbols = {str(sym).upper() for sym in universe.get("us", [])}
    india_bases = {_base_symbol(str(sym)) for sym in universe.get("india", [])}

    if upper not in us_symbols and upper in india_bases:
        normalized = f"{upper}.NS"
        return ResolvedAnalyzeSymbol(raw=raw, normalized=normalized, market="india", candidates=[normalized])

    return ResolvedAnalyzeSymbol(raw=raw, normalized=upper, market="us", candidates=[upper])


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


_WRITE_KEY_ENV = "MARKET_PULSE_WRITE_KEY"
_ALLOW_UNAUTH_WRITES_ENV = "MARKET_PULSE_ALLOW_UNAUTH_WRITES"
_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
_RULE_TYPE_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,40}$")


def _is_local_client(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


def _assert_write_allowed(request: Request) -> None:
    """Guard persistent mutations for public deployments.

    Local development stays frictionless. Public/server deployments should set
    MARKET_PULSE_WRITE_KEY and send it via X-API-Key, or explicitly set
    MARKET_PULSE_ALLOW_UNAUTH_WRITES=1 if they accept unauthenticated writes.
    """
    if os.getenv(_ALLOW_UNAUTH_WRITES_ENV) == "1":
        return
    configured_key = os.getenv(_WRITE_KEY_ENV)
    if configured_key:
        provided = request.headers.get("x-api-key")
        if provided == configured_key:
            return
        raise HTTPException(status_code=401, detail="valid X-API-Key required for write operation")
    if _is_local_client(request):
        return
    raise HTTPException(
        status_code=403,
        detail=f"write operations require {_WRITE_KEY_ENV} for non-local clients",
    )


def _validate_symbol(symbol: str) -> str:
    sym = symbol.strip().upper()
    if not sym or not _SYMBOL_RE.match(sym):
        raise HTTPException(status_code=400, detail="invalid symbol")
    return sym


def _validate_alert_condition(condition: object) -> dict:
    if not isinstance(condition, dict):
        raise HTTPException(status_code=400, detail="condition must be an object")
    encoded = json.dumps(condition, separators=(",", ":"))
    if len(encoded) > 4096:
        raise HTTPException(status_code=400, detail="condition too large")
    return condition


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
    from datetime import datetime, timezone

    resolved_symbol = resolve_analyze_symbol(symbol)
    raw = resolved_symbol.raw
    upper = resolved_symbol.normalized
    candidates = resolved_symbol.candidates

    if not refresh:
        async with state.lock:
            for sym in candidates:
                data = state.symbols.get(sym)
                if data:
                    return data

    # On-demand full analysis for any ticker (US, India, or UK)
    market = resolved_symbol.market
    norm_sym = resolved_symbol.normalized

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
    company_name = (
        (info or {}).get("longName")
        or (info or {}).get("shortName")
        or (info or {}).get("displayName")
        or norm_sym
    )
    payload = {
        "symbol": norm_sym,
        "name": company_name,
        "market": market,
        "score": sig.score,
        "signals": sig.signals,
        "alerts": sig.alerts,
        "metrics": {**(sig.metrics or {}), "name": company_name},
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
    safe_limit = max(1, min(limit, 500))
    db_news = await recent_news(safe_limit)
    snap = await state.snapshot()
    return {"live": snap.get("news", []), "stored": db_news, "limit": safe_limit}


@app.get("/api/watchlist")
async def api_watchlist():
    watches = await list_watchlist()
    return {"watches": watches, "count": len(watches)}


@app.post("/api/watchlist")
async def api_add_watchlist(request: Request, payload: dict = Body(...)):
    _assert_write_allowed(request)
    symbol = _validate_symbol(str(payload.get("symbol") or ""))
    notes = str(payload.get("notes") or "")[:500]
    ok = await add_to_watchlist(symbol, notes=notes)
    watches = await list_watchlist()
    async with state.lock:
        state.watches = watches
    state.broadcast_event.set()
    return {"ok": ok, "symbol": symbol, "watches": watches}


@app.delete("/api/watchlist/{symbol:path}")
async def api_delete_watchlist(symbol: str, request: Request):
    _assert_write_allowed(request)
    sym = _validate_symbol(symbol)
    await remove_from_watchlist(sym)
    watches = await list_watchlist()
    async with state.lock:
        state.watches = watches
    state.broadcast_event.set()
    return {"ok": True, "symbol": sym, "watches": watches}


@app.get("/api/alert_rules")
async def api_alert_rules():
    rules = await list_alert_rules()
    return {"rules": rules, "count": len(rules)}


@app.post("/api/alert_rules")
async def api_add_alert_rule(request: Request, payload: dict = Body(...)):
    _assert_write_allowed(request)
    rule_type = str(payload.get("rule_type") or "custom").strip() or "custom"
    if not _RULE_TYPE_RE.match(rule_type):
        raise HTTPException(status_code=400, detail="invalid rule_type")
    condition = _validate_alert_condition(payload.get("condition") or {})
    enabled = bool(payload.get("enabled", True))
    rule_id = await add_alert_rule(rule_type, condition, enabled=enabled)
    rules = await list_alert_rules()
    rule = next((r for r in rules if r.get("id") == rule_id), None)
    return {"ok": True, "id": rule_id, "rule": rule}


@app.delete("/api/alert_rules/{rule_id:int}")
async def api_delete_alert_rule(rule_id: int, request: Request):
    _assert_write_allowed(request)
    await delete_alert_rule(rule_id)
    return {"ok": True, "id": rule_id}


@app.get("/api/alerts/recent")
async def api_recent_alerts(limit: int = 50):
    safe_limit = max(1, min(limit, 200))
    alerts = await recent_alerts(limit=safe_limit)
    return {"alerts": alerts, "count": len(alerts), "limit": safe_limit}


def _as_positive_float(value, field: str, *, required: bool = False):
    if value is None or value == "":
        if required:
            raise HTTPException(status_code=400, detail=f"{field} required")
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field} must be numeric")
    if parsed <= 0:
        raise HTTPException(status_code=400, detail=f"{field} must be > 0")
    return parsed


def _current_row_for_symbol(symbol: str) -> dict | None:
    row = state.symbols.get(symbol)
    if not row and symbol.endswith((".NS", ".BO")):
        row = state.symbols.get(symbol.replace(".NS", "").replace(".BO", ""))
    return row


async def _portfolio_payload() -> dict:
    positions = await list_portfolio()
    stats = await get_performance_stats()
    open_value = 0.0
    open_pnl = 0.0
    enriched = []
    async with state.lock:
        symbols_cache = dict(state.symbols)
    for pos in positions:
        p = dict(pos)
        sym = p.get("symbol")
        row = symbols_cache.get(sym) or {}
        m = row.get("metrics") or {}
        current_price = m.get("price") or p.get("entry_price")
        qty = float(p.get("qty") or 0)
        entry = float(p.get("entry_price") or 0)
        if current_price is not None:
            try:
                cp = float(current_price)
                est_pnl = round((cp - entry) * qty, 2)
                p["current_price"] = cp
                p["est_pnl"] = est_pnl
                p["est_pnl_pct"] = round(((cp - entry) / entry * 100), 2) if entry else 0
                open_value += cp * qty
                open_pnl += est_pnl
            except Exception:
                pass
        p["current_buy"] = m.get("buy_score") or row.get("buy_score") or row.get("score")
        p["current_qual"] = m.get("quality_score") or row.get("quality_score")
        enriched.append(p)
    entry_value = round(sum(float(p.get("entry_price") or 0) * float(p.get("qty") or 0) for p in positions), 2)
    stats.update({
        "paper_equity_entry": entry_value,
        "total_paper_value_est": round(open_value, 2) if open_value else entry_value,
        "open_pnl_est": round(open_pnl, 2),
    })
    return {"positions": enriched, "stats": stats, "count": len(enriched)}


@app.get("/api/portfolio")
async def api_portfolio():
    return await _portfolio_payload()


@app.post("/api/portfolio")
async def api_add_portfolio(request: Request, payload: dict = Body(...)):
    _assert_write_allowed(request)
    symbol = _validate_symbol(str(payload.get("symbol") or ""))
    qty = _as_positive_float(payload.get("qty"), "qty", required=True)
    entry_price = _as_positive_float(payload.get("entry_price"), "entry_price", required=True)
    entry_score = payload.get("entry_score")
    if entry_score is not None and entry_score != "":
        try:
            entry_score = float(entry_score)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="entry_score must be numeric")
    notes = str(payload.get("notes") or "")[:1000] or None
    sl = _as_positive_float(payload.get("sl"), "sl")
    target = _as_positive_float(payload.get("target"), "target")
    market = str(payload.get("market") or ("india" if symbol.endswith((".NS", ".BO")) else "uk" if symbol.endswith(".L") else "us"))
    pos_id = await upsert_portfolio_position(symbol, market, qty, entry_price, entry_score, notes, sl, target)
    await record_trade_journal(symbol, "buy", price=entry_price, qty=qty, score_at_time=entry_score, notes=notes, linked_position_id=pos_id)
    return {"ok": True, "id": pos_id, **(await _portfolio_payload())}


@app.get("/api/journal")
async def api_journal(limit: int = 100):
    safe_limit = max(1, min(limit, 500))
    journal = await list_journal(limit=safe_limit)
    return {"journal": journal, "count": len(journal), "limit": safe_limit}


@app.post("/api/position/{symbol:path}/update")
async def api_update_position(symbol: str, request: Request, payload: dict = Body(...)):
    _assert_write_allowed(request)
    sym = _validate_symbol(symbol)
    notes = payload.get("notes")
    notes = str(notes)[:1000] if notes is not None else None
    sl = _as_positive_float(payload.get("sl"), "sl")
    target = _as_positive_float(payload.get("target"), "target")
    await update_portfolio_position(sym, notes=notes, sl=sl, target=target)
    return {"ok": True, **(await _portfolio_payload())}


@app.post("/api/position/{symbol:path}/close")
async def api_close_position(symbol: str, request: Request, payload: dict = Body(default_factory=dict)):
    _assert_write_allowed(request)
    sym = _validate_symbol(symbol)
    positions = await list_portfolio()
    pos = next((p for p in positions if (p.get("symbol") or "").upper() == sym), None)
    if not pos:
        raise HTTPException(status_code=404, detail="position not found")
    close_price = payload.get("price") or payload.get("close_price")
    if close_price is not None and close_price != "":
        close_price = _as_positive_float(close_price, "close_price", required=True)
    else:
        async with state.lock:
            row = dict(state.symbols.get(sym) or {})
        close_price = (row.get("metrics") or {}).get("price") or pos.get("entry_price")
        close_price = float(close_price)
    qty = float(pos.get("qty") or 0)
    entry = float(pos.get("entry_price") or 0)
    realized = round((close_price - entry) * qty, 2)
    await record_trade_journal(sym, "close", price=close_price, qty=qty, outcome_pnl=realized, notes=str(payload.get("notes") or pos.get("notes") or "")[:1000], linked_position_id=pos.get("id"))
    await delete_portfolio_position(sym)
    return {"ok": True, "symbol": sym, "outcome_pnl": realized, **(await _portfolio_payload())}


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


async def get_regime() -> dict:
    """Light stub regime awareness (high VIX or broad market trend) using a couple indices.
    Reuses yf (same as outcomes computation). Noted in edge response + UI; does not alter core scoring engine.
    """
    try:
        import yfinance as yf
        vix_hist = yf.download("^VIX", period="10d", progress=False, auto_adjust=True)
        vix = float(vix_hist["Close"].iloc[-1]) if not vix_hist.empty else 20.0
        # Broad US trend via SPY 1m vs 20d ago; simple bias
        spy_hist = yf.download("SPY", period="30d", progress=False, auto_adjust=True)
        trend = "neutral"
        if not spy_hist.empty and len(spy_hist) > 5:
            c_now = float(spy_hist["Close"].iloc[-1])
            c_20 = float(spy_hist["Close"].iloc[0])
            chg = (c_now / c_20 - 1) * 100
            trend = "bullish" if chg > 1.5 else ("bearish" if chg < -2.0 else "neutral")
        # India proxy (NIFTY 50 ETF or index) - tolerant
        try:
            ind_hist = yf.download("^NSEI", period="20d", progress=False, auto_adjust=True)
            ind_trend = "neutral"
            if not ind_hist.empty and len(ind_hist) > 3:
                ic_now = float(ind_hist["Close"].iloc[-1])
                ic_old = float(ind_hist["Close"].iloc[0])
                ind_trend = "bullish" if (ic_now / ic_old - 1) > 0.01 else ("bearish" if (ic_now / ic_old - 1) < -0.015 else "neutral")
            if ind_trend != "neutral":
                trend = ind_trend  # last one wins or could blend
        except Exception:
            pass
        high_vix = vix >= 25.0
        note = (
            "High VIX regime (>25) — size positions smaller, favor names with confidence_score >80 + quality"
            if high_vix else f"VIX ~{vix:.1f} · market {trend} bias"
        )
        return {
            "vix": round(vix, 1),
            "trend": trend,
            "high_vol": high_vix,
            "note": note,
            "as_of": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        return {"vix": 20.0, "trend": "neutral", "high_vol": False, "note": "regime data unavailable", "error": str(e)[:60]}


@app.get("/api/regime")
async def api_regime():
    """Lightweight market regime note (VIX + trend from indices). Used by edge + frontend pills."""
    return await get_regime()


@app.get("/api/edge")
async def api_edge(days: int = 2, min_score: float = 55.0):
    """Backtest / historical edge view with forward outcomes.
    Rich stats: hit rates by bucket for 1d/3d/7d/14d, max DD aggregates, confidence breakdowns,
    simple factor performance (which passed factors historically showed edge in snapshots).
    Uses recent_strong_snapshots_with_outcomes (enhanced yf-at-query-time with cache) + payload confidence/buy/quality from price_crawler + analyze engine.
    Self-validating; no new engine invented.
    """
    snaps = await recent_strong_snapshots_with_outcomes(days=days, min_score=min_score, limit=120)
    regime = await get_regime()

    # Group by approximate window (preserve full promoted fields for UI)
    by_time: dict[str, list] = {}
    for s in snaps:
        key = s.get("created_at", "")[:13]
        by_time.setdefault(key, []).append({
            "symbol": s["symbol"],
            "market": s.get("market"),
            "score": round(s.get("score", 0), 1),
            "buy_score": round(s.get("buy_score", s.get("score", 0)), 1),
            "quality_score": s.get("quality_score"),
            "confidence_score": s.get("confidence_score"),
            "created_at": s.get("created_at"),
            "has_smart_money": bool((s.get("payload") or {}).get("metrics", {}).get("smart_money", {}).get("hits")),
            "outcomes": s.get("outcomes"),
        })

    # Valid samples that have full forward outcomes (reuse the yf computed ones)
    valid = [s for s in snaps if s.get("outcomes") and s["outcomes"].get("ret_7d") is not None]
    total = len(valid)

    # Overall by horizon (rich: all 1d/3d/7d/14d)
    def horizon_stats(hkey):
        vals = [s["outcomes"].get(hkey) for s in valid if s["outcomes"].get(hkey) is not None]
        if not vals:
            return {"n": 0, "hit_rate": 0, "avg_ret": 0}
        hits = sum(1 for v in vals if v > 0)
        return {
            "n": len(vals),
            "hit_rate": round(hits / len(vals) * 100, 1),
            "avg_ret": round(sum(vals) / len(vals), 2),
        }

    overall = {
        "1d": horizon_stats("ret_1d"),
        "3d": horizon_stats("ret_3d"),
        "7d": horizon_stats("ret_7d"),
        "14d": horizon_stats("ret_14d"),
    }

    # Buckets by score (70+ etc) now with full horizons + max_dd
    score_buckets = {"70+": [], "60-70": [], "55-60": []}
    for s in valid:
        sc = s.get("buy_score") or s.get("score", 0)
        bucket = "70+" if sc >= 70 else ("60-70" if sc >= 60 else "55-60")
        score_buckets[bucket].append(s)

    bucket_stats = {}
    horizons = ["ret_1d", "ret_3d", "ret_7d", "ret_14d"]
    for b, items in score_buckets.items():
        if not items:
            continue
        bs = {"n": len(items)}
        for h in horizons:
            vals = [it["outcomes"].get(h) for it in items if it["outcomes"].get(h) is not None]
            if vals:
                hs = sum(1 for v in vals if v > 0)
                bs[h] = {
                    "hit_rate": round(hs / len(vals) * 100, 1),
                    "avg_ret": round(sum(vals) / len(vals), 2),
                    "n": len(vals),
                }
        # max DD for bucket
        dds = [it["outcomes"].get("max_dd_14d", 0) for it in items if it["outcomes"].get("max_dd_14d") is not None]
        if dds:
            bs["avg_max_dd_14d"] = round(sum(dds) / len(dds), 2)
            bs["worst_max_dd_14d"] = round(min(dds), 2)
        bucket_stats[b] = bs

    # Confidence breakdowns (reuse the confidence_score heuristic from price_crawler full scan + regular scan)
    conf_buckets = {"high>80": [], "med60-80": [], "low<60": []}
    for s in valid:
        c = s.get("confidence_score") or 70
        if c >= 80:
            conf_buckets["high>80"].append(s)
        elif c >= 60:
            conf_buckets["med60-80"].append(s)
        else:
            conf_buckets["low<60"].append(s)
    conf_breakdown = {}
    for cb, items in conf_buckets.items():
        if not items:
            continue
        vals7 = [it["outcomes"].get("ret_7d") for it in items if it["outcomes"].get("ret_7d") is not None]
        dds = [it["outcomes"].get("max_dd_14d", 0) for it in items if it["outcomes"].get("max_dd_14d") is not None]
        cb_stats = {"n": len(items)}
        if vals7:
            hs = sum(1 for v in vals7 if v > 0)
            cb_stats["hit_7d"] = round(hs / len(vals7) * 100, 1)
            cb_stats["avg_ret7d"] = round(sum(vals7) / len(vals7), 2)
        if dds:
            cb_stats["avg_max_dd"] = round(sum(dds)/len(dds), 2)
        conf_breakdown[cb] = cb_stats

    # Overall max DD aggregates
    all_dds = [s["outcomes"].get("max_dd_14d") for s in valid if s["outcomes"].get("max_dd_14d") is not None]
    mdd_summary = {}
    if all_dds:
        mdd_summary = {
            "avg_max_dd_14d": round(sum(all_dds) / len(all_dds), 2),
            "median_max_dd_14d": round(sorted(all_dds)[len(all_dds)//2], 2),
            "n": len(all_dds),
        }

    # Simple factor performance mini table (which factors had best historical edge from snapshots)
    # Reuses factor_breakdown already stored in payloads from engine (scoring + factor_registry)
    from collections import defaultdict
    factor_perf = defaultdict(lambda: {"n": 0, "pos7": 0, "sum_ret7": 0.0, "sum_dd": 0.0, "dd_n": 0})
    for s in valid:
        fb = s.get("factor_breakdown") or []
        ret7 = s["outcomes"].get("ret_7d")
        dd = s["outcomes"].get("max_dd_14d")
        for f in fb:
            if (f.get("status") or "").lower() != "pass":
                continue
            fid = f.get("id") or f.get("name") or str(f)[:30]
            fp = factor_perf[fid]
            fp["n"] += 1
            if ret7 is not None:
                fp["sum_ret7"] += ret7
                if ret7 > 0:
                    fp["pos7"] += 1
            if dd is not None:
                fp["sum_dd"] += dd
                fp["dd_n"] += 1
    # rank by hit rate + sample size + avg ret; keep top ~8
    factor_rows = []
    for fid, st in factor_perf.items():
        if st["n"] < 2:
            continue
        hit = round(st["pos7"] / st["n"] * 100, 1) if st["n"] else 0
        avg_r = round(st["sum_ret7"] / st["n"], 2) if st["n"] else 0
        avg_d = round(st["sum_dd"] / st["dd_n"], 2) if st["dd_n"] else 0
        factor_rows.append({
            "factor": fid,
            "n": st["n"],
            "hit_rate_7d": hit,
            "avg_ret_7d": avg_r,
            "avg_max_dd": avg_d,
        })
    factor_rows.sort(key=lambda x: (x["hit_rate_7d"], x["n"], x["avg_ret_7d"]), reverse=True)
    top_factor_edge = factor_rows[:8]

    # Legacy bucket_stats kept for compat (now 7d focused), plus new rich ones
    legacy_buckets = {"70+": [], "60-70": [], "55-60": []}
    for s in valid:
        sc = s.get("buy_score") or s.get("score", 0)
        if sc >= 70:
            legacy_buckets["70+"].append(s["outcomes"]["ret_7d"])
        elif sc >= 60:
            legacy_buckets["60-70"].append(s["outcomes"]["ret_7d"])
        else:
            legacy_buckets["55-60"].append(s["outcomes"]["ret_7d"])
    legacy_bucket_stats = {}
    for b, rets in legacy_buckets.items():
        if rets:
            legacy_bucket_stats[b] = {
                "n": len(rets),
                "hit_rate": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
                "avg_ret7d": round(sum(rets) / len(rets), 2),
            }

    summary = {
        "windows": len(by_time),
        "total_signals": len(snaps),
        "valid_with_outcomes": total,
        # rich horizon stats
        "overall": overall,
        "hit_rate_7d": overall.get("7d", {}).get("hit_rate", 0),
        "avg_ret_7d": overall.get("7d", {}).get("avg_ret", 0),
        # legacy compat
        "bucket_stats": legacy_bucket_stats,
        # new rich bucket + mdd + conf + factors
        "bucket_stats_by_horizon": bucket_stats,
        "mdd_summary": mdd_summary,
        "confidence_breakdown": conf_breakdown,
        "top_factor_edge": top_factor_edge,
        "min_score": min_score,
        "days": days,
        "regime": regime,
    }
    return {"summary": summary, "signals": snaps[:60], "by_window": by_time, "regime": regime}


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
                market = "india" if sym.endswith((".NS", ".BO")) else "uk" if sym.endswith(".L") else "us"
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


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """Serve the React SPA shell for client-side routes (e.g. /watchlist, /sectors).

    Registered last so explicit /api routes, the /static mount, and /ws all match
    first. Real API misses still return JSON 404 rather than the HTML shell.
    """
    if full_path.startswith(("api/", "static/", "ws")):
        raise HTTPException(status_code=404, detail="not found")
    index_path = FRONTEND / "index.html"
    if index_path.exists():
        return FileResponse(
            index_path,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {"message": "Market Pulse API — frontend missing"}


def run():
    import uvicorn

    cfg = load_config()
    host = cfg.get("server", {}).get("host", "0.0.0.0")
    # PORT env var takes precedence (standard on Railway, Render, Fly.io, Heroku, etc.)
    port = int(os.getenv("PORT") or cfg.get("server", {}).get("port", 8765))
    uvicorn.run("app.main:app", host=host, port=port, reload=False, proxy_headers=True)


if __name__ == "__main__":
    run()
