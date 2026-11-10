import base64
import unittest
from risk.holders import (
    aggregate_owner_amounts, base58_encode, concentration_from_amounts,
)


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

    def test_owner_wallets_are_aggregated(self):
        owner_a = bytes([1]) * 32
        owner_b = bytes([2]) * 32

        def account(owner, amount):
            raw = bytearray(165)
            raw[32:64] = owner
            raw[64:72] = amount.to_bytes(8, "little")
            return {"data": [base64.b64encode(raw).decode(), "base64"]}

        owners, parsed = aggregate_owner_amounts([
            account(owner_a, 40), account(owner_a, 30), account(owner_b, 20)
        ])
        self.assertEqual(parsed, 3)
        self.assertEqual(len(owners), 2)
        self.assertEqual(sorted(owners.values(), reverse=True), [70, 20])
        self.assertEqual(len(base58_encode(owner_a)), 44)


if __name__ == "__main__":
    unittest.main()
