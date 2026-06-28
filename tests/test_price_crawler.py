from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import app.crawler.price_crawler as pc


def hist(rows: int = 12) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": list(range(1, rows + 1)),
            "Volume": [100_000] * rows,
        }
    )


def sig(score: float, buy_score: float | None = None, quality_score: float = 70):
    if buy_score is None:
        buy_score = score
    return SimpleNamespace(
        score=score,
        signals=["ok"],
        alerts=[],
        metrics={"buy_score": buy_score, "quality_score": quality_score},
        factors_hit=1,
        factors_total=2,
        factor_details=[],
        factor_breakdown=[],
    )


class PriceCrawlerScanSymbolsTests(unittest.TestCase):
    def test_scan_symbols_accepts_non_empty_dataframe(self):
        inserts = []

        async def fake_insert(symbol, market, payload, score):
            inserts.append((symbol, market, score))

        info = {"shortName": "Apple", **{f"k{i}": i for i in range(10)}}
        with (
            patch.object(pc, "_fetch_batch_with_status", return_value={"AAPL": (hist(12), info, None, "test_provider")}),
            patch.object(pc, "analyze_symbol", return_value=sig(61, buy_score=61, quality_score=72)),
            patch.object(pc, "annotate_ml_intel", lambda results: None),
            patch.object(pc, "insert_snapshot", fake_insert),
        ):
            results = asyncio.run(pc.scan_symbols(["AAPL"], "us", {}, {}))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["symbol"], "AAPL")
        self.assertEqual(results[0]["buy_score"], 61)
        self.assertEqual(results[0]["quality_score"], 72)
        self.assertEqual(results[0]["provider_status"], "test_provider")
        self.assertEqual(inserts, [("AAPL", "us", 61)])

    def test_scan_symbols_skips_none_empty_and_short_history(self):
        calls = []

        def fake_analyze(*args, **kwargs):
            calls.append(args)
            return sig(50)

        cases = [
            {"NONE": (None, {}, None, "test_provider")},
            {"EMPTY": (pd.DataFrame(), {}, None, "test_provider")},
            {"SHORT": (hist(9), {}, None, "test_provider")},
        ]

        for raw in cases:
            with self.subTest(raw=list(raw.keys())[0]):
                with (
                    patch.object(pc, "_fetch_batch_with_status", return_value=raw),
                    patch.object(pc, "analyze_symbol", fake_analyze),
                    patch.object(pc, "annotate_ml_intel", lambda results: None),
                ):
                    results = asyncio.run(pc.scan_symbols(list(raw.keys()), "us", {}, {}))
                self.assertEqual(results, [])

        self.assertEqual(calls, [])

    def test_scan_symbols_sorts_by_buy_score_not_raw_score(self):
        def fake_analyze(symbol, *args, **kwargs):
            if symbol == "RAW_HIGH":
                return sig(score=99, buy_score=40)
            if symbol == "BUY_HIGH":
                return sig(score=60, buy_score=80)
            raise AssertionError(symbol)

        async def fake_insert(*args, **kwargs):
            return None

        with (
            patch.object(
                pc,
                "_fetch_batch_with_status",
                return_value={
                    "RAW_HIGH": (hist(12), {}, None, "test_provider"),
                    "BUY_HIGH": (hist(12), {}, None, "test_provider"),
                },
            ),
            patch.object(pc, "analyze_symbol", fake_analyze),
            patch.object(pc, "annotate_ml_intel", lambda results: None),
            patch.object(pc, "insert_snapshot", fake_insert),
        ):
            results = asyncio.run(pc.scan_symbols(["RAW_HIGH", "BUY_HIGH"], "us", {}, {}))

        self.assertEqual([r["symbol"] for r in results], ["BUY_HIGH", "RAW_HIGH"])

    def test_provider_layer_uses_stooq_for_live_us_and_leaves_misses_for_last_good_cache(self):
        with (
            patch.object(pc, "_fetch_stooq_batch", return_value={"AAPL": (hist(12), {"provider": "stooq"}, None)}),
            patch.object(pc, "_fetch_history_batch") as yf_history,
            patch.object(pc, "_fetch_batch") as yf_full,
        ):
            raw = pc._fetch_batch_with_status(["AAPL", "MSFT"], "us")

        yf_history.assert_not_called()
        yf_full.assert_not_called()
        self.assertEqual(raw["AAPL"][3], "stooq")
        self.assertNotIn("MSFT", raw)

    def test_provider_layer_can_opt_into_yahoo_info_for_deep_ad_hoc_analysis(self):
        with (
            patch.object(pc, "_fetch_stooq_batch", return_value={}),
            patch.object(pc, "_fetch_batch", return_value={"MSFT": (hist(12), {"longName": "Microsoft"}, {"earningsDate": []})}) as full_batch,
            patch.object(pc, "_fetch_history_batch") as hist_batch,
        ):
            raw = pc._fetch_batch_with_status(["MSFT"], "us", include_info=True)

        full_batch.assert_called_once_with(["MSFT"])
        hist_batch.assert_not_called()
        self.assertEqual(raw["MSFT"][1]["longName"], "Microsoft")
        self.assertEqual(raw["MSFT"][3], "yfinance_fallback")

    def test_scan_symbols_uses_last_good_snapshot_without_reinserting_stale_rows(self):
        inserts = []

        async def fake_insert(*args, **kwargs):
            inserts.append(args)

        async def fake_latest(symbols, *, max_age_hours=24):
            return {
                symbols[0]: {
                    "symbol": symbols[0],
                    "market": "us",
                    "score": 71,
                    "buy_score": 71,
                    "metrics": {"buy_score": 71},
                    "stale": True,
                    "provider_status": "last_good_snapshot",
                }
            }

        with (
            patch.object(pc, "_fetch_batch_with_status", return_value={}),
            patch.object(pc, "annotate_ml_intel", lambda results: None),
            patch.object(pc, "latest_snapshot_payloads", fake_latest),
            patch.object(pc, "insert_snapshot", fake_insert),
        ):
            results = asyncio.run(pc.scan_symbols(["AAPL"], "us", {}, {}))

        self.assertEqual(results[0]["symbol"], "AAPL")
        self.assertTrue(results[0]["stale"])
        self.assertEqual(inserts, [])


if __name__ == "__main__":
    unittest.main()
