import unittest
from intelligence.scoring import score_token


class ScoringTests(unittest.TestCase):
    def good_token(self):
        return {"liquidity_usd": 50000, "volume_1h": 25000,
                "buys_1h": 80, "sells_1h": 30, "price_change_1h": 12}

    def test_good_market_data_is_ranked(self):
        result = score_token(self.good_token())
        self.assertGreater(result["score"], 0)
        self.assertIn(result["decision"], {"WATCH", "MONITOR", "SKIP"})

    def test_low_liquidity_is_rejected(self):
        token = self.good_token()
        token["liquidity_usd"] = 100
        self.assertEqual(score_token(token)["decision"], "REJECT")

    def test_fresh_pair_uses_five_minute_activity(self):\n        token = {"liquidity_usd": 12000, "volume_5m": 1800,\n                 "buys_5m": 28, "sells_5m": 5, "price_change_5m": 8}\n        result = score_token(token, min_liquidity=5000, min_volume_1h=250,\n                             min_txns_1h=8, fresh=True)\n        self.assertGreater(result["score"], 0)\n        self.assertNotEqual(result["decision"], "REJECT")\n\n    def test_fresh_pair_rejects_low_five_minute_activity(self):\n        token = {"liquidity_usd": 12000, "volume_5m": 10,\n                 "buys_5m": 1, "sells_5m": 0, "price_change_5m": 0}\n        result = score_token(token, min_liquidity=5000, min_volume_1h=250,\n                             min_txns_1h=8, fresh=True)\n        self.assertEqual(result["decision"], "REJECT")\n\n    def test_malformed_and_nan_values_do_not_crash(self):
        token = {"liquidity_usd": "bad", "volume_1h": float("nan"),
                 "buys_1h": None, "sells_1h": "?", "price_change_1h": "inf"}
        result = score_token(token)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["score"], 0)


if __name__ == "__main__":
    unittest.main()
