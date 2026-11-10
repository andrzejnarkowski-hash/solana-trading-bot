import tempfile
import unittest
from pathlib import Path
from trading.paper import PaperBroker


class PaperBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bot = PaperBroker(
            db_path=Path(self.tmp.name) / "test.sqlite3",
            starting_balance=100, trade_size=25, max_positions=2,
            stop_loss_pct=20, take_profit_pct=40,
        )
    def tearDown(self):
        self.tmp.cleanup()
    def token(self, address="mint1", price=1.0):
        return {"address": address, "symbol": "TEST", "price_usd": price}
    def test_open_and_take_profit(self):
        self.assertTrue(self.bot.open_position(self.token(), 80))
        self.assertFalse(self.bot.open_position(self.token(), 80))
        closed = self.bot.update_positions({"mint1": 1.5})
        self.assertEqual(closed[0][2], "TAKE_PROFIT")
        self.assertAlmostEqual(self.bot.summary()["realized_pnl"], 12.5)
    def test_stop_loss(self):
        self.bot.open_position(self.token(), 80)
        closed = self.bot.update_positions({"mint1": 0.7})
        self.assertEqual(closed[0][2], "STOP_LOSS")
        self.assertAlmostEqual(self.bot.summary()["realized_pnl"], -7.5)
    def test_position_limit_and_cash(self):
        self.assertTrue(self.bot.open_position(self.token("a"), 80))
        self.assertTrue(self.bot.open_position(self.token("b"), 80))
        self.assertFalse(self.bot.open_position(self.token("c"), 80))
        self.assertEqual(self.bot.summary()["cash"], 50)


if __name__ == "__main__":
    unittest.main()
