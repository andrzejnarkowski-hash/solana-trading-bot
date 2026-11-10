"""Conservative SQLite paper broker with configurable execution friction.

No wallet, signing, or real transactions. All prices supplied by the scanner are
market observations; simulated fills include adverse slippage and fees.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "bot.sqlite3"


class PaperBroker:
    def __init__(
        self, db_path=DB_PATH, starting_balance=1000.0, trade_size=25.0,
        max_positions=5, stop_loss_pct=20.0, take_profit_pct=40.0,
        fee_bps=100.0, slippage_bps=150.0, cooldown_minutes=60,
        max_daily_loss_pct=10.0,
    ):
        self.db_path = str(db_path)
        self.starting_balance = max(0.0, float(starting_balance))
        self.trade_size = max(0.0, float(trade_size))
        self.max_positions = max(1, int(max_positions))
        self.stop_loss_pct = max(0.1, float(stop_loss_pct))
        self.take_profit_pct = max(0.1, float(take_profit_pct))
        self.fee_rate = max(0.0, float(fee_bps)) / 10000.0
        self.slippage_rate = max(0.0, float(slippage_bps)) / 10000.0
        self.cooldown_seconds = max(0, int(cooldown_minutes * 60))
        self.max_daily_loss_pct = max(0.0, float(max_daily_loss_pct))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        con = sqlite3.connect(self.db_path, timeout=15)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self):
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK(id=1),
                starting_balance REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL, symbol TEXT, entry_price REAL NOT NULL,
                exit_price REAL, quantity REAL NOT NULL, invested_usd REAL NOT NULL,
                pnl_usd REAL, status TEXT NOT NULL, opened_at INTEGER NOT NULL,
                closed_at INTEGER, exit_reason TEXT,
                entry_fee_usd REAL NOT NULL DEFAULT 0,
                exit_fee_usd REAL NOT NULL DEFAULT 0,
                entry_slippage_bps REAL NOT NULL DEFAULT 0,
                exit_slippage_bps REAL NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
            CREATE INDEX IF NOT EXISTS idx_trades_address_time ON trades(address, opened_at);
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT, address TEXT NOT NULL,
                symbol TEXT, price_usd REAL, liquidity_usd REAL, volume_1h REAL,
                score REAL, decision TEXT, scanned_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_time ON snapshots(scanned_at);
            CREATE INDEX IF NOT EXISTS idx_snapshots_address_time ON snapshots(address, scanned_at);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, level TEXT NOT NULL,
                message TEXT NOT NULL, created_at INTEGER NOT NULL
            );
            """)
            # Backward-compatible schema migration for existing paper databases.
            columns = {row["name"] for row in db.execute("PRAGMA table_info(trades)")}
            migrations = {
                "entry_fee_usd": "REAL NOT NULL DEFAULT 0",
                "exit_fee_usd": "REAL NOT NULL DEFAULT 0",
                "entry_slippage_bps": "REAL NOT NULL DEFAULT 0",
                "exit_slippage_bps": "REAL NOT NULL DEFAULT 0",
            }
            for name, declaration in migrations.items():
                if name not in columns:
                    db.execute(f"ALTER TABLE trades ADD COLUMN {name} {declaration}")
            db.execute("INSERT OR IGNORE INTO account(id, starting_balance) VALUES(1, ?)",
                       (self.starting_balance,))

    def log(self, message, level="INFO"):
        with self._connect() as db:
            db.execute("INSERT INTO events(level,message,created_at) VALUES(?,?,?)",
                       (level, str(message)[:1000], int(time.time())))

    def record_snapshot(self, token, score, decision):
        price = self._positive(token.get("price_usd"))
        with self._connect() as db:
            db.execute("""INSERT INTO snapshots
                (address,symbol,price_usd,liquidity_usd,volume_1h,score,decision,scanned_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (token.get("address"), token.get("symbol"), price,
                 self._positive(token.get("liquidity_usd")),
                 self._positive(token.get("volume_1h")), float(score or 0),
                 str(decision), int(time.time())))

    @staticmethod
    def _positive(value):
        try:
            number = float(value)
            return number if number > 0 and number < float("inf") else 0.0
        except (TypeError, ValueError, OverflowError):
            return 0.0

    def _cash(self, db):
        start = db.execute("SELECT starting_balance FROM account WHERE id=1").fetchone()[0]
        spent = db.execute(
            "SELECT COALESCE(SUM(invested_usd + entry_fee_usd),0) FROM trades WHERE status='OPEN'"
        ).fetchone()[0]
        realized = db.execute(
            "SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='CLOSED'"
        ).fetchone()[0]
        return float(start + realized - spent)

    def _daily_loss_limit_hit(self, db, now):
        if self.max_daily_loss_pct <= 0:
            return False
        day_start = now - (now % 86400)
        row = db.execute(
            "SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='CLOSED' AND closed_at>=?",
            (day_start,),
        ).fetchone()
        realized_today = float(row[0] or 0)
        baseline = max(self.starting_balance, 1.0)
        return realized_today <= -(baseline * self.max_daily_loss_pct / 100.0)

    def open_position(self, token, score):
        address = token.get("address")
        market_price = self._positive(token.get("price_usd"))
        if not address or market_price <= 0:
            return False
        now = int(time.time())
        with self._connect() as db:
            existing = db.execute(
                "SELECT 1 FROM trades WHERE address=? AND status='OPEN'", (address,)
            ).fetchone()
            recent = db.execute(
                "SELECT MAX(opened_at) FROM trades WHERE address=?", (address,)
            ).fetchone()[0]
            count = db.execute("SELECT COUNT(*) n FROM trades WHERE status='OPEN'").fetchone()["n"]
            cash = self._cash(db)
            size = min(self.trade_size, cash / (1 + self.fee_rate))
            if (existing or count >= self.max_positions or size <= 0 or
                    self._daily_loss_limit_hit(db, now) or
                    (recent and now - int(recent) < self.cooldown_seconds)):
                return False
            execution_price = market_price * (1 + self.slippage_rate)
            quantity = size / execution_price
            entry_fee = size * self.fee_rate
            db.execute("""INSERT INTO trades
                (address,symbol,entry_price,quantity,invested_usd,status,opened_at,
                 entry_fee_usd,entry_slippage_bps)
                VALUES(?,?,?,?,?,'OPEN',?,?,?)""",
                (address, token.get("symbol"), execution_price, quantity, size,
                 now, entry_fee, self.slippage_rate * 10000))
        self.log(
            f"PAPER BUY {token.get('symbol')} | score {score} | notional ${size:.2f} "
            f"| entry fee ${entry_fee:.2f} | slippage {self.slippage_rate*100:.2f}%",
        )
        return True

    def update_positions(self, prices):
        closed = []
        with self._connect() as db:
            rows = db.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()
            for row in rows:
                market_price = self._positive(prices.get(row["address"]))
                if not market_price:
                    continue
                exit_price = market_price * (1 - self.slippage_rate)
                gross_proceeds = row["quantity"] * exit_price
                exit_fee = gross_proceeds * self.fee_rate
                net_proceeds = gross_proceeds - exit_fee
                total_cost = row["invested_usd"] + row["entry_fee_usd"]
                pnl = net_proceeds - total_cost
                pnl_pct = pnl / max(total_cost, 1e-12) * 100
                reason = ("STOP_LOSS" if pnl_pct <= -self.stop_loss_pct else
                          "TAKE_PROFIT" if pnl_pct >= self.take_profit_pct else None)
                if reason:
                    db.execute("""UPDATE trades SET status='CLOSED',exit_price=?,pnl_usd=?,
                        closed_at=?,exit_reason=?,exit_fee_usd=?,exit_slippage_bps=? WHERE id=?""",
                        (exit_price, pnl, int(time.time()), reason, exit_fee,
                         self.slippage_rate * 10000, row["id"]))
                    closed.append((row["symbol"], pnl, reason))
        for symbol, pnl, reason in closed:
            self.log(f"PAPER SELL {symbol} | {reason} | net P&L ${pnl:.2f}")
        return closed

    def summary(self, prices=None):
        prices = prices or {}
        with self._connect() as db:
            start = float(db.execute("SELECT starting_balance FROM account WHERE id=1").fetchone()[0])
            cash = self._cash(db)
            rows = db.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()
            realized = float(db.execute(
                "SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='CLOSED'"
            ).fetchone()[0])
            unrealized = 0.0
            positions = []
            for row in rows:
                market = self._positive(prices.get(row["address"])) or row["entry_price"]
                liquidation_price = market * (1 - self.slippage_rate)
                gross = liquidation_price * row["quantity"]
                exit_fee = gross * self.fee_rate
                net_value = gross - exit_fee
                cost = row["invested_usd"] + row["entry_fee_usd"]
                pnl = net_value - cost
                unrealized += pnl
                item = dict(row)
                item.update({
                    "market_price_usd": market,
                    "estimated_net_value_usd": round(net_value, 6),
                    "unrealized_pnl_usd": round(pnl, 6),
                    "unrealized_pnl_pct": round(pnl / max(cost, 1e-12) * 100, 3),
                })
                positions.append(item)
            equity = cash + sum(
                self._positive(prices.get(row["address"])) * row["quantity"] *
                (1 - self.slippage_rate) * (1 - self.fee_rate)
                if self._positive(prices.get(row["address"])) else
                row["quantity"] * row["entry_price"] * (1 - self.slippage_rate) * (1 - self.fee_rate)
                for row in rows
            )
            return {
                "starting_balance": start, "cash": cash, "equity": equity,
                "realized_pnl": realized, "unrealized_pnl": unrealized,
                "open_positions": len(rows), "positions": positions,
                "total_pnl": equity - start,
            }

    def performance(self):
        with self._connect() as db:
            rows = db.execute(
                "SELECT pnl_usd, opened_at, closed_at FROM trades WHERE status='CLOSED' ORDER BY closed_at"
            ).fetchall()
            wins = [float(r["pnl_usd"] or 0) for r in rows if float(r["pnl_usd"] or 0) > 0]
            losses = [float(r["pnl_usd"] or 0) for r in rows if float(r["pnl_usd"] or 0) < 0]
            total = len(rows)
            gross_profit, gross_loss = sum(wins), abs(sum(losses))
            return {
                "closed_trades": total,
                "win_rate_pct": round(len(wins) / total * 100, 2) if total else 0.0,
                "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else (None if gross_profit == 0 else "inf"),
                "average_pnl_usd": round(sum(float(r["pnl_usd"] or 0) for r in rows) / total, 4) if total else 0.0,
                "best_trade_usd": max((float(r["pnl_usd"] or 0) for r in rows), default=0.0),
                "worst_trade_usd": min((float(r["pnl_usd"] or 0) for r in rows), default=0.0),
            }

    def recent_trades(self, limit=100):
        with self._connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (max(1, min(int(limit), 1000)),)
            )]

    def recent_snapshots(self, limit=100):
        with self._connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM snapshots ORDER BY id DESC LIMIT ?", (max(1, min(int(limit), 5000)),)
            )]

    def recent_events(self, limit=100):
        with self._connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (max(1, min(int(limit), 1000)),)
            )]
