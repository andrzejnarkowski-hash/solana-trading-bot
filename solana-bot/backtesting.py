"""Snapshot-based backtester with delayed entries and execution friction.

This is a research aid, not a live-fill simulator. It uses only snapshots actually
recorded by this bot and explicitly charges fees and adverse slippage on both sides.
"""


def run_backtest(snapshots, starting_balance=1000.0, trade_size=25.0,
                 max_positions=5, stop_loss_pct=20.0, take_profit_pct=40.0,
                 fee_bps=100.0, slippage_bps=150.0, cooldown_minutes=60):
    fee = max(0.0, float(fee_bps)) / 10000.0
    slip = max(0.0, float(slippage_bps)) / 10000.0
    start = max(0.0, float(starting_balance))
    cash = start
    size_setting = max(0.0, float(trade_size))
    max_positions = max(1, int(max_positions))
    cooldown = max(0, int(cooldown_minutes * 60))
    stop = max(0.1, float(stop_loss_pct))
    target = max(0.1, float(take_profit_pct))

    rows = []
    for item in snapshots or []:
        try:
            address = str(item.get("address") or "")
            price = float(item.get("price_usd") or 0)
            stamp = int(item.get("scanned_at") or 0)
            if address and 0 < price < float("inf") and stamp > 0:
                rows.append({**item, "address": address, "price_usd": price, "scanned_at": stamp})
        except (TypeError, ValueError, OverflowError):
            continue
    rows.sort(key=lambda x: (x["scanned_at"], x["address"]))

    pending, opened, last_entry = {}, {}, {}
    trades, curve = [], []
    peak, max_dd = max(start, 1e-12), 0.0

    def close(address, market_price, stamp, reason):
        nonlocal cash
        pos = opened.pop(address)
        exit_price = market_price * (1 - slip)
        gross = pos["quantity"] * exit_price
        exit_fee = gross * fee
        net = gross - exit_fee
        pnl = net - pos["cost"]
        cash += net
        trades.append({
            "address": address, "symbol": pos["symbol"],
            "entry_time": pos["entry_time"], "exit_time": stamp,
            "entry_price": pos["entry_price"], "exit_price": exit_price,
            "invested_usd": pos["notional"], "entry_fee_usd": pos["entry_fee"],
            "exit_fee_usd": exit_fee, "pnl_usd": pnl,
            "return_pct": pnl / pos["cost"] * 100, "exit_reason": reason,
        })

    for row in rows:
        address, price, stamp = row["address"], row["price_usd"], row["scanned_at"]
        if address in opened:
            pos = opened[address]
            gross = pos["quantity"] * price * (1 - slip)
            net = gross * (1 - fee)
            net_return = (net - pos["cost"]) / pos["cost"] * 100
            if net_return <= -stop:
                close(address, price, stamp, "STOP_LOSS")
            elif net_return >= target:
                close(address, price, stamp, "TAKE_PROFIT")
            if address in opened:
                opened[address]["last_price"] = price
                opened[address]["last_time"] = stamp
        elif address in pending:
            signal_time = pending.pop(address)
            if (stamp > signal_time and len(opened) < max_positions and
                    stamp - last_entry.get(address, 0) >= cooldown):
                notional = min(size_setting, cash / (1 + fee))
                if notional > 0:
                    entry_price = price * (1 + slip)
                    entry_fee = notional * fee
                    cost = notional + entry_fee
                    cash -= cost
                    opened[address] = {
                        "symbol": row.get("symbol"), "entry_price": entry_price,
                        "quantity": notional / entry_price, "notional": notional,
                        "entry_fee": entry_fee, "cost": cost,
                        "entry_time": stamp, "last_price": price, "last_time": stamp,
                    }
                    last_entry[address] = stamp

        if address not in opened and row.get("decision") == "WATCH":
            pending[address] = stamp

        equity = cash
        for pos in opened.values():
            equity += pos["quantity"] * pos["last_price"] * (1 - slip) * (1 - fee)
        curve.append({"timestamp": stamp, "equity": equity})
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100 if peak else 0.0)

    for address in list(opened):
        pos = opened[address]
        close(address, pos["last_price"], pos["last_time"], "END_OF_DATA")

    pnl = cash - start
    wins = [t["pnl_usd"] for t in trades if t["pnl_usd"] > 0]
    losses = [t["pnl_usd"] for t in trades if t["pnl_usd"] < 0]
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    return {
        "starting_balance": start, "ending_balance": cash, "net_pnl_usd": pnl,
        "return_pct": pnl / max(start, 1e-12) * 100,
        "closed_trades": len(trades),
        "win_rate_pct": len(wins) / len(trades) * 100 if trades else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else (None if not gross_profit else float("inf")),
        "max_drawdown_pct": max_dd, "trades": trades, "equity_curve": curve,
        "assumptions": {
            "entry_delay": "One subsequent snapshot per token",
            "fee_bps_each_side": fee_bps, "slippage_bps_each_side": slippage_bps,
            "note": "Snapshots only; missing candles, liquidity impact, MEV, RPC gaps and failed fills are not reconstructed.",
        },
    }
