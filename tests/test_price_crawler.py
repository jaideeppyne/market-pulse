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
            patch.object(pc, "_fetch_batch", return_value={"AAPL": (hist(12), info, None)}),
            patch.object(pc, "analyze_symbol", return_value=sig(61, buy_score=61, quality_score=72)),
            patch.object(pc, "annotate_ml_intel", lambda results: None),
            patch.object(pc, "insert_snapshot", fake_insert),
        ):
            results = asyncio.run(pc.scan_symbols(["AAPL"], "us", {}, {}))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["symbol"], "AAPL")
        self.assertEqual(results[0]["buy_score"], 61)
        self.assertEqual(results[0]["quality_score"], 72)
        self.assertEqual(inserts, [("AAPL", "us", 61)])

    def test_scan_symbols_skips_none_empty_and_short_history(self):
        calls = []

        def fake_analyze(*args, **kwargs):
            calls.append(args)
            return sig(50)

        cases = [
            {"NONE": (None, {}, None)},
            {"EMPTY": (pd.DataFrame(), {}, None)},
            {"SHORT": (hist(9), {}, None)},
        ]

        for raw in cases:
            with self.subTest(raw=list(raw.keys())[0]):
                with (
                    patch.object(pc, "_fetch_batch", return_value=raw),
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
                "_fetch_batch",
                return_value={
                    "RAW_HIGH": (hist(12), {}, None),
                    "BUY_HIGH": (hist(12), {}, None),
                },
            ),
            patch.object(pc, "analyze_symbol", fake_analyze),
            patch.object(pc, "annotate_ml_intel", lambda results: None),
            patch.object(pc, "insert_snapshot", fake_insert),
        ):
            results = asyncio.run(pc.scan_symbols(["RAW_HIGH", "BUY_HIGH"], "us", {}, {}))

        self.assertEqual([r["symbol"] for r in results], ["BUY_HIGH", "RAW_HIGH"])


if __name__ == "__main__":
    unittest.main()
