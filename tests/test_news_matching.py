import unittest

from app.engine.smart_money_intel import analyze_smart_money
from app.universe import extract_tickers_from_text


class NewsTickerMatchingTests(unittest.TestCase):
    def test_stocks_in_focus_does_not_match_focus_ticker(self):
        universe = {"FOCUS.NS", "AAPL", "RELIANCE.NS"}

        found = extract_tickers_from_text("Stocks in focus today: banks and IT shares", universe)

        self.assertNotIn("FOCUS.NS", found)

    def test_ambiguous_common_words_require_explicit_ticker_context(self):
        universe = {"HAS", "ARE", "NOW", "META"}

        found = extract_tickers_from_text("Markets are strong now and earnings has momentum", universe)

        self.assertEqual(found, [])

    def test_meta_infotech_does_not_match_meta_platforms_without_explicit_context(self):
        universe = {"META"}

        found = extract_tickers_from_text("Meta Infotech promoter buys shares in IPO", universe)

        self.assertEqual(found, [])

    def test_meta_platforms_alias_matches_meta(self):
        universe = {"META"}

        found = extract_tickers_from_text("Meta Platforms reports strong AI ad growth", universe)

        self.assertEqual(found, ["META"])

    def test_non_equity_property_purchase_does_not_trigger_smart_money_buy(self):
        intel = analyze_smart_money(
            ["Madhusudan Kela buys luxury apartment in DLF project"],
            market="india",
        )

        self.assertFalse(intel.matches)
        self.assertFalse(intel.india_legend)


if __name__ == "__main__":
    unittest.main()
