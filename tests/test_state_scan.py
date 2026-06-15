import asyncio
import unittest

from app.state import AppState


def run_state_update(state: AppState, coro):
    loop = state.lock._loop or asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        asyncio.set_event_loop(loop)


def make_state() -> AppState:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return AppState()


class AppStateScanTests(unittest.TestCase):
    def test_update_scan_tracks_empty_full_scan_observability(self):
        state = make_state()

        run_state_update(
            state,
            state.update_scan(
                [],
                threshold=55,
                partial=False,
                batch_index=1,
                batch_total=1,
                attempted_count=3,
            ),
        )

        self.assertEqual(state.stats["symbols_tracked"], 0)
        self.assertEqual(state.stats["last_full_price_scan_attempted"], 3)
        self.assertEqual(state.stats["last_full_price_scan_result_count"], 0)
        self.assertIs(state.stats["last_full_price_scan_empty"], True)
        self.assertIn("last_empty_price_scan", state.stats)
        self.assertIn("last_price_scan", state.stats)
        self.assertTrue(state.broadcast_event.is_set())

    def test_update_news_tracks_result_and_symbol_observability(self):
        state = make_state()
        items = [
            {"title": "ACME wins order", "symbols": ["ACME", "BETA"]},
            {"title": "No ticker macro headline", "symbols": []},
        ]
        counts = {"ACME": 2, "BETA": 1}
        titles = {"ACME": ["ACME wins order"], "BETA": ["BETA follows"]}

        run_state_update(state, state.update_news(items, counts, titles))

        self.assertEqual(state.stats["news_count"], 2)
        self.assertEqual(state.stats["last_news_scan_result_count"], 2)
        self.assertEqual(state.stats["last_news_scan_symbol_count"], 2)
        self.assertIs(state.stats["last_news_scan_empty"], False)
        self.assertIn("last_news_scan", state.stats)
        self.assertTrue(state.broadcast_event.is_set())

    def test_update_candidates_tracks_empty_light_scan_observability(self):
        state = make_state()

        run_state_update(state, state.update_candidates([]))

        self.assertEqual(state.stats["candidate_count"], 0)
        self.assertEqual(state.stats["last_light_scan_result_count"], 0)
        self.assertIs(state.stats["last_light_scan_empty"], True)
        self.assertIn("last_empty_light_scan", state.stats)
        self.assertIn("last_light_scan", state.stats)
        self.assertTrue(state.broadcast_event.is_set())

    def test_update_events_tracks_empty_scan_observability(self):
        state = make_state()

        run_state_update(state, state.update_events([]))

        self.assertEqual(state.stats["market_events_count"], 0)
        self.assertEqual(state.stats["last_event_scan_result_count"], 0)
        self.assertIs(state.stats["last_event_scan_empty"], True)
        self.assertIn("last_empty_event_scan", state.stats)
        self.assertIn("last_event_scan", state.stats)
        self.assertTrue(state.broadcast_event.is_set())

    def test_hot_lists_rank_and_filter_by_buy_score(self):
        state = make_state()
        rows = [
            {
                "symbol": "RAW_HIGH",
                "market": "us",
                "score": 99,
                "buy_score": 10,
                "metrics": {"buy_score": 10, "quality_score": 40},
            },
            {
                "symbol": "BUY_HIGH",
                "market": "us",
                "score": 50,
                "buy_score": 80,
                "metrics": {"buy_score": 80, "quality_score": 70},
            },
        ]

        run_state_update(
            state,
            state.update_scan(
                rows,
                threshold=0,
                partial=False,
                batch_index=1,
                batch_total=1,
                attempted_count=2,
            ),
        )

        self.assertEqual(state.hot[0]["symbol"], "BUY_HIGH")
        self.assertEqual(state.hot_by_market["us"][0]["symbol"], "BUY_HIGH")

    def test_hot_count_uses_buy_score_threshold(self):
        state = make_state()
        rows = [
            {
                "symbol": "RAW_HIGH",
                "market": "us",
                "score": 99,
                "buy_score": 10,
                "metrics": {"buy_score": 10},
            },
            {
                "symbol": "BUY_HIGH",
                "market": "us",
                "score": 50,
                "buy_score": 80,
                "metrics": {"buy_score": 80},
            },
        ]

        run_state_update(
            state,
            state.update_scan(
                rows,
                threshold=55,
                partial=False,
                batch_index=1,
                batch_total=1,
                attempted_count=2,
            ),
        )

        self.assertEqual(state.stats["hot_count"], 1)
        self.assertEqual(state.hot[0]["symbol"], "BUY_HIGH")


if __name__ == "__main__":
    unittest.main()
