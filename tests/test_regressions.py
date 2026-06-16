from __future__ import annotations

import asyncio
from datetime import datetime, timezone


def run(coro):
    return asyncio.run(coro)


def test_api_news_returns_stored_news(tmp_path):
    from app import db, main
    from app.state import AppState

    db.DB_PATH = tmp_path / "market_pulse.db"
    main.DB_PATH = db.DB_PATH
    main.state = AppState()

    run(db.init_db())
    run(
        db.insert_news(
            "2026-06-15T10:00:00+00:00",
            "ACME beats estimates",
            "https://example.com/acme",
            "Test Feed",
            "us",
            ["ACME"],
        )
    )

    result = run(main.api_news(limit=5))

    assert result["stored"][0]["title"] == "ACME beats estimates"
    assert result["stored"][0]["symbols"] == ["ACME"]


def test_alert_rule_evaluator_triggers_on_score_and_rvol(tmp_path):
    from app import db

    db.DB_PATH = tmp_path / "market_pulse.db"
    run(db.init_db())
    rule_id = run(db.add_alert_rule("score", {"min_buy_score": 65, "min_rvol": 2.0}, True))

    result = run(
        db.evaluate_rules_for_snapshot(
            {
                "hot": [
                    {
                        "symbol": "ACME",
                        "score": 80,
                        "metrics": {"buy_score": 80, "rvol": 3.0, "name": "ACME Corp"},
                    }
                ]
            }
        )
    )

    # Rich evaluator output (includes condition, ts, standardized reasons, investor fields, float buy_score)
    assert len(result) == 1
    trig = result[0]
    assert trig["symbol"] == "ACME"
    assert trig["rule_id"] == rule_id
    assert trig["rule_type"] == "score"
    assert "buy_score 80.0 >= 65" in trig["message"]
    assert trig["buy_score"] == 80.0 or trig["buy_score"] == 80
    det = trig["details"]
    assert det["buy_score"] == 80.0 or det["buy_score"] == 80
    assert det["rvol"] == 3.0
    assert "buy_score" in det["reasons"][0].lower() or "buy score" in det["reasons"][0].lower()
    assert "has_investor" in det


def test_state_news_earnings_buzz_parses_date():
    from app.state import AppState

    state = AppState()
    title = "ACME Q1 results on 15 Jul expected after market close"
    run(state.update_news([{"title": title, "symbols": ["ACME.NS"]}], {"ACME.NS": 1}))

    snapshot = run(state.snapshot())

    item = next(e for e in snapshot["earnings"] if e["symbol"] == "ACME.NS")
    assert item["from_news"] is True
    assert item["earnings_date"] != "news"
    assert item["days_until"] is not None
    assert item["earnings_date"].endswith("-07-15")
    assert int(item["earnings_date"][:4]) >= datetime.now(timezone.utc).year



def test_analyze_resolver_prefers_plain_us_ticker_when_symbol_exists_in_us_universe():
    from app import main

    main.state.universe = {
        "us": ["AAPL", "MRVL"],
        "india": ["RELIANCE.NS", "TCS.NS"],
        "uk": ["BP.L"],
    }

    resolved = main.resolve_analyze_symbol("MRVL")

    assert resolved.normalized == "MRVL"
    assert resolved.market == "us"
    assert resolved.candidates == ["MRVL"]


def test_analyze_resolver_still_maps_known_india_alias_to_ns_suffix():
    from app import main

    main.state.universe = {
        "us": ["AAPL", "MRVL"],
        "india": ["RELIANCE.NS", "TCS.NS"],
        "uk": ["BP.L"],
    }

    resolved = main.resolve_analyze_symbol("reliance")

    assert resolved.normalized == "RELIANCE.NS"
    assert resolved.market == "india"
    assert resolved.candidates == ["RELIANCE.NS"]


def test_live_price_scan_pairs_come_from_configured_universe_not_hardcoded_core():
    from app.state import AppState
    from app.workers.scanner_loop import ScannerLoop

    state = AppState()
    state.universe = {
        "us": ["AAPL", "MRVL", "ZZZ"],
        "india": ["RELIANCE.NS"],
        "uk": ["BP.L"],
    }
    scanner = ScannerLoop(
        {
            "scanner": {"live_symbols_per_market": 10},
        },
        state,
    )

    pairs = scanner._build_live_scan_pairs({})

    assert ("MRVL", "us") in pairs
    assert ("ZZZ", "us") in pairs
    assert ("RELIANCE.NS", "india") in pairs
    assert ("BP.L", "uk") in pairs
