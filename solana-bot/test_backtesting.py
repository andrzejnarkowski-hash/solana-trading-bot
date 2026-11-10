import unittest
from backtesting import run_backtest


class BacktestTests(unittest.TestCase):
    def test_entries_are_delayed_until_next_observation(self):
        result = run_backtest([
            {"address": "mint", "symbol": "T", "price_usd": 10, "decision": "WATCH", "scanned_at": 100},
        ], starting_balance=1000, trade_size=100)
        self.assertEqual(result["closed_trades"], 0)

    def test_costs_are_charged_and_take_profit_closes_trade(self):
        result = run_backtest([
            {"address": "mint", "symbol": "T", "price_usd": 10, "decision": "WATCH", "scanned_at": 100},
            {"address": "mint", "symbol": "T", "price_usd": 10, "decision": "WATCH", "scanned_at": 160},
            {"address": "mint", "symbol": "T", "price_usd": 12, "decision": "WATCH", "scanned_at": 220},
        ], starting_balance=1000, trade_size=100, take_profit_pct=5,
           fee_bps=100, slippage_bps=100, cooldown_minutes=0)
        self.assertEqual(result["closed_trades"], 1)
        trade = result["trades"][0]
        self.assertEqual(trade["entry_time"], 160)
        self.assertEqual(trade["exit_reason"], "TAKE_PROFIT")
        self.assertGreater(trade["entry_fee_usd"], 0)
        self.assertGreater(trade["exit_fee_usd"], 0)
        self.assertGreater(result["net_pnl_usd"], 0)

    def test_invalid_snapshot_rows_are_skipped(self):
        result = run_backtest([{"address": "bad", "price_usd": "nan", "scanned_at": 10}])
        self.assertEqual(result["closed_trades"], 0)


if __name__ == "__main__":
    unittest.main()
