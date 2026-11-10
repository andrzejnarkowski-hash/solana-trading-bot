import unittest
from risk.holders import concentration_from_amounts


class HolderConcentrationTests(unittest.TestCase):
    def test_top_account_shares(self):
        result = concentration_from_amounts([40, 30, 10, 20], 100)
        self.assertEqual(result["top10_token_account_share_pct"], 100.0)
        self.assertEqual(result["top20_token_account_share_pct"], 100.0)

    def test_partial_account_list_is_not_fabricated(self):
        result = concentration_from_amounts([10, 5], 100)
        self.assertEqual(result["top20_token_account_share_pct"], 15.0)

    def test_missing_supply_returns_none(self):
        self.assertIsNone(concentration_from_amounts([10], 0))


if __name__ == "__main__":
    unittest.main()
