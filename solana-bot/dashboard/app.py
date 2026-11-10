import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
import os
from dotenv import load_dotenv
load_dotenv()
import pandas as pd
from trading.paper import PaperBroker

st.set_page_config(page_title="Solana Paper Trader", page_icon="📈", layout="wide")
st.title("Solana Meme Scanner — Paper Trading")
st.caption("Simulation only. No wallet connection and no real trades.")
broker = PaperBroker(
    starting_balance=float(os.getenv("PAPER_START_BALANCE_USD", "1000")),
    trade_size=float(os.getenv("PAPER_TRADE_SIZE_USD", "25")),
    max_positions=int(os.getenv("PAPER_MAX_OPEN_POSITIONS", "5")),
    stop_loss_pct=float(os.getenv("PAPER_STOP_LOSS_PCT", "20")),
    take_profit_pct=float(os.getenv("PAPER_TAKE_PROFIT_PCT", "40")),
)
summary = broker.summary()
c1,c2,c3,c4 = st.columns(4)
c1.metric("Paper equity", f"${summary['equity']:,.2f}")
c2.metric("Available cash", f"${summary['cash']:,.2f}")
c3.metric("Realized P&L", f"${summary['realized_pnl']:,.2f}")
c4.metric("Open positions", summary["open_positions"])
st.subheader("Open positions")
positions = summary["positions"]
if positions:
    st.dataframe(pd.DataFrame(positions), use_container_width=True, hide_index=True)
else:
    st.info("No open paper positions yet. Start bot.py and let it scan.")
st.subheader("Recent market signals")
signals = broker.recent_snapshots(100)
if signals:
    st.dataframe(pd.DataFrame(signals), use_container_width=True, hide_index=True)
else:
    st.info("No scans recorded yet.")
st.subheader("Trade history")
trades = broker.recent_trades(100)
if trades:
    st.dataframe(pd.DataFrame(trades), use_container_width=True, hide_index=True)
st.subheader("Bot events")
events = broker.recent_events(100)
if events:
    st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
st.caption("Refresh the page to update. Stop-loss and take-profit are evaluated on each scan cycle; slippage, priority fees and DEX execution are not simulated.")
