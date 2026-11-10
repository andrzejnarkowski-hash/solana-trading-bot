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

    def test_malformed_and_nan_values_do_not_crash(self):
        token = {"liquidity_usd": "bad", "volume_1h": float("nan"),
                 "buys_1h": None, "sells_1h": "?", "price_change_1h": "inf"}
        result = score_token(token)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["score"], 0)


if __name__ == "__main__":
    unittest.main()
