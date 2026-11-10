import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
import pandas as pd
from config import settings
from trading.paper import PaperBroker
from backtesting import run_backtest

st.set_page_config(page_title="Solana Paper Trader", page_icon="📈", layout="wide")
st.title("Solana Meme Scanner — Paper Trading")
st.caption("Simulation only. No wallet connection, signing, or real transactions.")
st.sidebar.caption("Paper execution assumptions")
st.sidebar.write(f"Fee: {settings.paper_fee_bps:.0f} bps per side")
st.sidebar.write(f"Slippage: {settings.paper_slippage_bps:.0f} bps per side")
st.sidebar.write(f"Stop-loss: {settings.paper_stop_loss_pct:.1f}% net")
st.sidebar.write(f"Take-profit: {settings.paper_take_profit_pct:.1f}% net")
st.sidebar.write(f"Daily loss guard: {settings.paper_max_daily_loss_pct:.1f}%")
st.sidebar.caption("Refresh the page to load the latest bot data.")

broker = PaperBroker(
    starting_balance=settings.paper_start_balance_usd,
    trade_size=settings.paper_trade_size_usd,
    max_positions=settings.paper_max_open_positions,
    stop_loss_pct=settings.paper_stop_loss_pct,
    take_profit_pct=settings.paper_take_profit_pct,
    fee_bps=settings.paper_fee_bps,
    slippage_bps=settings.paper_slippage_bps,
    cooldown_minutes=settings.paper_cooldown_minutes,
    max_daily_loss_pct=settings.paper_max_daily_loss_pct,
)
all_snapshots = broker.recent_snapshots(5000)
latest_prices = {}
for snapshot in all_snapshots:
    address = snapshot.get("address")
    price = snapshot.get("price_usd")
    if address and address not in latest_prices and price:
        latest_prices[address] = price
summary = broker.summary(latest_prices)
performance = broker.performance()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Paper equity", f"${summary['equity']:,.2f}", f"${summary['total_pnl']:,.2f} total")
c2.metric("Available cash", f"${summary['cash']:,.2f}")
c3.metric("Realized P&L", f"${summary['realized_pnl']:,.2f}")
c4.metric("Open positions", summary["open_positions"])

st.subheader("Closed-trade performance")
p1, p2, p3, p4 = st.columns(4)
p1.metric("Closed trades", performance["closed_trades"])
p2.metric("Win rate", f"{performance['win_rate_pct']:.1f}%")
pf = performance["profit_factor"]
p3.metric("Profit factor", "∞" if pf == "inf" else ("—" if pf is None else f"{pf:.2f}"))
p4.metric("Average net P&L", f"${performance['average_pnl_usd']:.2f}")

st.subheader("Open positions")
positions = summary["positions"]
if positions:
    st.dataframe(pd.DataFrame(positions), use_container_width=True, hide_index=True)
else:
    st.info("No open paper positions yet. Start the bot and let it scan.")

st.subheader("Trade history")
trades = broker.recent_trades(200)
if trades:
    st.dataframe(pd.DataFrame(trades), use_container_width=True, hide_index=True)
else:
    st.info("No paper trades have been opened yet.")

st.subheader("Market snapshots")
signals = all_snapshots[:200]
if signals:
    st.dataframe(pd.DataFrame(signals), use_container_width=True, hide_index=True)
else:
    st.info("No scans recorded yet.")

st.subheader("Backtest recorded snapshots")
st.caption(
    "Uses your saved scanner observations, delays entries until the next observation for each token, "
    "and charges the configured fees and slippage. It cannot recreate missing candles or fills."
)
if st.button("Run backtest on saved data", type="primary"):
    history = broker.recent_snapshots(5000)
    result = run_backtest(
        history,
        starting_balance=settings.paper_start_balance_usd,
        trade_size=settings.paper_trade_size_usd,
        max_positions=settings.paper_max_open_positions,
        stop_loss_pct=settings.paper_stop_loss_pct,
        take_profit_pct=settings.paper_take_profit_pct,
        fee_bps=settings.paper_fee_bps,
        slippage_bps=settings.paper_slippage_bps,
        cooldown_minutes=settings.paper_cooldown_minutes,
    )
    st.session_state["backtest_result"] = result

result = st.session_state.get("backtest_result")
if result:
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Backtest net P&L", f"${result['net_pnl_usd']:.2f}")
    b2.metric("Return", f"{result['return_pct']:.2f}%")
    b3.metric("Win rate", f"{result['win_rate_pct']:.1f}%")
    b4.metric("Max drawdown", f"{result['max_drawdown_pct']:.2f}%")
    st.write(f"Closed trades: {result['closed_trades']} | Profit factor: " +
             ("∞" if result["profit_factor"] == "inf" else
              ("—" if result["profit_factor"] is None else f"{result['profit_factor']:.2f}")))
    if result["equity_curve"]:
        curve = pd.DataFrame(result["equity_curve"]).set_index("timestamp")
        st.line_chart(curve["equity"])
    if result["trades"]:
        st.dataframe(pd.DataFrame(result["trades"]), use_container_width=True, hide_index=True)
    with st.expander("Backtest assumptions and limitations"):
        st.json(result["assumptions"])

st.subheader("Bot events")
events = broker.recent_events(100)
if events:
    st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
else:
    st.info("No bot events recorded yet.")
