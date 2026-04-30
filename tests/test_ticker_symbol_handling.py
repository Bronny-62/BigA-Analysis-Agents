import unittest

import pytest

from cli.utils import normalize_ticker_symbol
from tradingagents.agents.utils.agent_utils import build_instrument_context


@pytest.mark.unit
class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_accepts_tushare_ts_code(self):
        self.assertEqual(normalize_ticker_symbol(" 000001.sz "), "000001.SZ")
        self.assertEqual(normalize_ticker_symbol("600000.SH"), "600000.SH")

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context("300750.SZ")
        self.assertIn("300750.SZ", context)
        self.assertIn("Tushare ts_code", context)

    def test_normalize_ticker_symbol_rejects_non_a_share_symbol(self):
        with self.assertRaises(ValueError):
            normalize_ticker_symbol("NVDA")


if __name__ == "__main__":
    unittest.main()
