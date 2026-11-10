import tempfile
import unittest
from pathlib import Path

from trading.paper import PaperBroker


class PaperBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "paper.sqlite3"
        self.broker = PaperBroker(
            db_path=self.db, starting_balance=1000, trade_size=100,
            max_positions=2, stop_loss_pct=5, take_profit_pct=5,
            fee_bps=100, slippage_bps=100, cooldown_minutes=60,
            max_daily_loss_pct=0,
        )
        self.token = {"address": "mint-1", "symbol": "TEST", "price_usd": 10}

    def tearDown(self):
        self.tmp.cleanup()

    def test_entry_charges_fee_and_adverse_slippage(self):
        self.assertTrue(self.broker.open_position(self.token, 80))
        position = self.broker.summary()["positions"][0]
        self.assertGreater(position["entry_price"], 10)
        self.assertAlmostEqual(position["entry_fee_usd"], 1.0)
        self.assertAlmostEqual(self.broker.summary()["cash"], 899.0, places=5)

    def test_duplicate_position_is_blocked(self):
        self.assertTrue(self.broker.open_position(self.token, 80))
        self.assertFalse(self.broker.open_position(self.token, 80))

    def test_exit_pnl_is_net_of_both_sides_costs(self):
        self.assertTrue(self.broker.open_position(self.token, 80))
        closed = self.broker.update_positions({"mint-1": 12})
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0][2], "TAKE_PROFIT")
        self.assertGreater(closed[0][1], 0)
        self.assertAlmostEqual(self.broker.summary()["cash"], 1000 + closed[0][1], places=5)
        self.assertGreater(self.broker.performance()["win_rate_pct"], 0)

    def test_cooldown_blocks_immediate_reentry(self):
        self.assertTrue(self.broker.open_position(self.token, 80))
        self.broker.update_positions({"mint-1": 12})
        self.assertFalse(self.broker.open_position(self.token, 80))


    def test_daily_loss_guard_blocks_new_entries(self):
        guarded = PaperBroker(
            db_path=Path(self.tmp.name) / "guarded.sqlite3",
            starting_balance=1000, trade_size=100, stop_loss_pct=5,
            take_profit_pct=50, fee_bps=100, slippage_bps=100,
            max_daily_loss_pct=1,
        )
        self.assertTrue(guarded.open_position(self.token, 80))
        guarded.update_positions({"mint-1": 9})
        self.assertFalse(guarded.open_position(
            {"address": "mint-2", "symbol": "NEXT", "price_usd": 1}, 80
        ))

    def test_bad_prices_are_ignored(self):
        self.assertFalse(self.broker.open_position({**self.token, "price_usd": "nan"}, 80))
        self.assertFalse(self.broker.open_position({**self.token, "price_usd": -1}, 80))


if __name__ == "__main__":
    unittest.main()
