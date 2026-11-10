import unittest
from scanner.dexscreener import DexScreener


class ScannerTests(unittest.TestCase):
    def test_analyze_pair_handles_missing_and_bad_numbers(self):
        pair = {"baseToken": {"address": "mint", "symbol": "T"},
                "priceUsd": "not-a-price", "liquidity": {"usd": None},
                "volume": {"h1": "NaN"}, "txns": {"h1": {"buys": "3"}}}
        token = DexScreener().analyze_pair(pair)
        self.assertEqual(token["price_usd"], 0)
        self.assertEqual(token["liquidity_usd"], 0)
        self.assertEqual(token["volume_1h"], 0)
        self.assertEqual(token["buys_1h"], 3)

    def test_number_of_malformed_inputs_is_safe(self):
        token = DexScreener().analyze_pair({"baseToken": {}, "priceUsd": "inf"})
        self.assertEqual(token["price_usd"], 0)


if __name__ == "__main__":
    unittest.main()
