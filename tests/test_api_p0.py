import asyncio
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import db, main


async def _reset_state():
    async with main.state.lock:
        main.state.symbols = {}
        main.state.hot = []
        main.state.hot_by_market = {}
        main.state.news = []
        main.state.events = []
        main.state.events_by_symbol = {}
        main.state.earnings = []
        main.state.earnings_by_symbol = {}
        main.state.watches = []
        main.state.recent_server_alerts = []
        main.state.investor_events = []
        main.state.stats = {}


class ApiP0Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db_path = db.DB_PATH
        self.old_main_db_path = main.DB_PATH
        test_db = Path(self.tmp.name) / "market_pulse_test.db"
        db.DB_PATH = test_db
        main.DB_PATH = test_db
        asyncio.run(db.init_db())
        asyncio.run(_reset_state())
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        main.DB_PATH = self.old_main_db_path
        self.tmp.cleanup()

    def test_news_route_returns_stored_news(self):
        asyncio.run(
            db.insert_news(
                published_at="2026-06-15T10:00:00+00:00",
                title="AAPL test headline",
                link="https://example.com/aapl",
                source="test",
                market="us",
                symbols=["AAPL"],
            )
        )

        res = self.client.get("/api/news?limit=5")

        self.assertEqual(res.status_code, 200, res.text)
        payload = res.json()
        self.assertIn("live", payload)
        self.assertIn("stored", payload)
        self.assertEqual(payload["stored"][0]["title"], "AAPL test headline")
        self.assertEqual(payload["stored"][0]["symbols"], ["AAPL"])

    def test_watchlist_routes_persist_and_delete_symbols(self):
        res = self.client.get("/api/watchlist")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["watches"], [])

        res = self.client.post("/api/watchlist", json={"symbol": "aapl", "notes": "manual"})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIs(res.json()["ok"], True)
        self.assertEqual(res.json()["symbol"], "AAPL")

        res = self.client.get("/api/watchlist")
        self.assertEqual(res.status_code, 200, res.text)
        watches = res.json()["watches"]
        self.assertEqual(len(watches), 1)
        self.assertEqual(watches[0]["symbol"], "AAPL")
        self.assertEqual(watches[0]["notes"], "manual")

        res = self.client.delete("/api/watchlist/AAPL")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIs(res.json()["ok"], True)

        res = self.client.get("/api/watchlist")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["watches"], [])

    def test_alert_rule_routes_persist_list_and_delete_rules(self):
        res = self.client.get("/api/alert_rules")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["rules"], [])

        res = self.client.post(
            "/api/alert_rules",
            json={
                "rule_type": "score",
                "condition": {"min_buy_score": 65, "min_rvol": 2},
                "enabled": True,
            },
        )
        self.assertEqual(res.status_code, 200, res.text)
        created = res.json()
        self.assertIs(created["ok"], True)
        self.assertIsInstance(created["id"], int)

        res = self.client.get("/api/alert_rules")
        self.assertEqual(res.status_code, 200, res.text)
        rules = res.json()["rules"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], created["id"])
        self.assertEqual(rules[0]["rule_type"], "score")
        self.assertIs(rules[0]["enabled"], True)
        self.assertEqual(rules[0]["condition"], {"min_buy_score": 65, "min_rvol": 2})

        res = self.client.delete(f"/api/alert_rules/{created['id']}")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIs(res.json()["ok"], True)

        res = self.client.get("/api/alert_rules")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["rules"], [])

    def test_recent_alerts_route_returns_persisted_alerts(self):
        alert_id = asyncio.run(
            db.insert_alert(
                symbol="MSFT",
                message="Test persisted alert",
                rule_id=None,
                rule_type="score",
                buy_score=71,
                details={"reason": "unit-test"},
            )
        )

        res = self.client.get("/api/alerts/recent?limit=10")

        self.assertEqual(res.status_code, 200, res.text)
        payload = res.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["alerts"][0]["id"], alert_id)
        self.assertEqual(payload["alerts"][0]["symbol"], "MSFT")
        self.assertEqual(payload["alerts"][0]["message"], "Test persisted alert")
        self.assertEqual(payload["alerts"][0]["details"], {"reason": "unit-test"})

    def test_evaluate_rules_for_snapshot_matches_score_rvol_and_investor(self):
        rule_id = asyncio.run(
            db.add_alert_rule(
                "smart_money",
                {
                    "min_buy_score": 65,
                    "min_rvol": 2,
                    "has_investor": True,
                    "investor_types": ["us_legend"],
                },
                enabled=True,
            )
        )

        row = {
            "symbol": "AAPL",
            "score": 70,
            "metrics": {
                "buy_score": 72,
                "rvol": 2.4,
                "has_smart_money": True,
                "smart_money": {
                    "primary_alert": "🚨 Investor: Warren Buffett bought AAPL",
                    "hits": [
                        {
                            "name": "Warren Buffett",
                            "kind": "us_legend",
                            "tier": "S+",
                            "headline": "Warren Buffett bought AAPL",
                        }
                    ],
                },
            },
            "alerts": ["🚨 Investor: Warren Buffett bought AAPL"],
        }

        triggers = asyncio.run(db.evaluate_rules_for_snapshot({"hot": [row]}, [row]))

        self.assertEqual(len(triggers), 1)
        trig = triggers[0]
        self.assertEqual(trig["symbol"], "AAPL")
        self.assertEqual(trig["rule_id"], rule_id)
        self.assertEqual(trig["rule_type"], "smart_money")
        self.assertEqual(trig["buy_score"], 72)
        self.assertIn("Warren Buffett", trig["message"])
        self.assertIs(trig["details"]["has_investor"], True)
        self.assertIn("us_legend", trig["details"]["investor_types"])

    def test_evaluate_rules_for_snapshot_does_not_match_when_thresholds_fail(self):
        asyncio.run(
            db.add_alert_rule(
                "score",
                {"min_buy_score": 80, "min_rvol": 3},
                enabled=True,
            )
        )

        row = {
            "symbol": "AAPL",
            "score": 70,
            "metrics": {"buy_score": 72, "rvol": 2.4},
        }

        triggers = asyncio.run(db.evaluate_rules_for_snapshot({"hot": [row]}, [row]))
        self.assertEqual(triggers, [])

    def test_evaluate_rules_respects_explicit_zero_buy_score(self):
        asyncio.run(db.add_alert_rule("score", {"min_buy_score": 50}, enabled=True))
        row = {
            "symbol": "ZERO",
            "score": 90,
            "metrics": {"buy_score": 0, "rvol": 9.0},
        }

        triggers = asyncio.run(db.evaluate_rules_for_snapshot({"hot": [row]}, [row]))

        self.assertEqual(triggers, [])

    def test_evaluate_rules_for_snapshot_matches_earnings_rule(self):
        rule_id = asyncio.run(
            db.add_alert_rule("earnings", {"earnings_within_days": 3}, enabled=True)
        )

        row = {
            "symbol": "MSFT",
            "score": 62,
            "metrics": {"buy_score": 64, "rvol": 1.3, "days_until_earnings": 2},
        }

        triggers = asyncio.run(db.evaluate_rules_for_snapshot({"hot": [row]}, [row]))

        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["symbol"], "MSFT")
        self.assertEqual(triggers[0]["rule_id"], rule_id)
        self.assertIn("earnings", " ".join(triggers[0]["details"]["reasons"]).lower())

    def test_evaluate_and_fire_alerts_updates_rule_last_triggered_and_auto_watch(self):
        rule_id = asyncio.run(db.add_alert_rule("score", {"min_buy_score": 65}, enabled=True))
        row = {"symbol": "NVDA", "score": 70, "metrics": {"buy_score": 70, "rvol": 1.1}}

        fired = asyncio.run(main._evaluate_and_fire_alerts({"hot": [row]}, [row]))

        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]["symbol"], "NVDA")

        alerts = asyncio.run(db.recent_alerts(limit=5))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["symbol"], "NVDA")
        self.assertEqual(alerts[0]["rule_id"], rule_id)

        rules = asyncio.run(db.list_alert_rules())
        self.assertEqual(rules[0]["id"], rule_id)
        self.assertIsNotNone(rules[0]["last_triggered"])

        watches = asyncio.run(db.list_watchlist())
        self.assertEqual([w["symbol"] for w in watches], ["NVDA"])

    def test_repeated_alert_fire_dedupes_persisted_alert_rows(self):
        asyncio.run(db.add_alert_rule("score", {"min_buy_score": 65}, enabled=True))
        row = {"symbol": "AMD", "score": 70, "metrics": {"buy_score": 70, "rvol": 1.1}}

        asyncio.run(main._evaluate_and_fire_alerts({"hot": [row]}, [row]))
        asyncio.run(main._evaluate_and_fire_alerts({"hot": [row]}, [row]))

        alerts = asyncio.run(db.recent_alerts(limit=10))
        self.assertEqual(len([a for a in alerts if a["symbol"] == "AMD"]), 1)

    def test_insert_investor_event_persists_without_unique_conflict(self):
        asyncio.run(
            db.insert_investor_event(
                {
                    "symbol": "AAPL",
                    "event_type": "insider_buy",
                    "investor_name": "Test Investor",
                    "investor_quality": "test",
                    "details": "unit-test",
                    "source": "test",
                }
            )
        )
        asyncio.run(
            db.insert_investor_event(
                {
                    "symbol": "AAPL",
                    "event_type": "insider_buy",
                    "investor_name": "Test Investor 2",
                    "investor_quality": "test",
                    "details": "unit-test-2",
                    "source": "test",
                }
            )
        )

        async def count_rows():
            import aiosqlite
            async with aiosqlite.connect(db.DB_PATH) as conn:
                cur = await conn.execute("SELECT COUNT(*) FROM investor_events WHERE symbol = 'AAPL'")
                row = await cur.fetchone()
                return row[0]

        self.assertEqual(asyncio.run(count_rows()), 2)


if __name__ == "__main__":
    unittest.main()
