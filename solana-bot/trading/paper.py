"""Deterministic paper broker. No wallet, signing, or real transactions."""
from __future__ import annotations
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "bot.sqlite3"


class PaperBroker:
    def __init__(self, db_path=DB_PATH, starting_balance=1000.0,
                 trade_size=25.0, max_positions=5, stop_loss_pct=20.0,
                 take_profit_pct=40.0):
        self.db_path = str(db_path)
        self.starting_balance = float(starting_balance)
        self.trade_size = float(trade_size)
        self.max_positions = int(max_positions)
        self.stop_loss_pct = float(stop_loss_pct)
        self.take_profit_pct = float(take_profit_pct)
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
                closed_at INTEGER, exit_reason TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT, address TEXT NOT NULL,
                symbol TEXT, price_usd REAL, liquidity_usd REAL, volume_1h REAL,
                score REAL, decision TEXT, scanned_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_time ON snapshots(scanned_at);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, level TEXT NOT NULL,
                message TEXT NOT NULL, created_at INTEGER NOT NULL
            );
            """)
            db.execute("INSERT OR IGNORE INTO account(id, starting_balance) VALUES(1, ?)",
                       (self.starting_balance,))

    def log(self, message, level="INFO"):
        with self._connect() as db:
            db.execute("INSERT INTO events(level,message,created_at) VALUES(?,?,?)",
                       (level, str(message)[:1000], int(time.time())))

    def record_snapshot(self, token, score, decision):
        with self._connect() as db:
            db.execute("""INSERT INTO snapshots
                (address,symbol,price_usd,liquidity_usd,volume_1h,score,decision,scanned_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (token.get("address"), token.get("symbol"), float(token.get("price_usd") or 0),
                 float(token.get("liquidity_usd") or 0), float(token.get("volume_1h") or 0),
                 float(score or 0), decision, int(time.time())))

    def open_position(self, token, score):
        address = token.get("address")
        price = float(token.get("price_usd") or 0)
        if not address or price <= 0:
            return False
        with self._connect() as db:
            existing = db.execute(
                "SELECT 1 FROM trades WHERE address=? AND status='OPEN'", (address,)
            ).fetchone()
            count = db.execute("SELECT COUNT(*) n FROM trades WHERE status='OPEN'").fetchone()["n"]
            cash = self._cash(db)
            size = min(self.trade_size, cash)
            if existing or count >= self.max_positions or size <= 0:
                return False
            db.execute("""INSERT INTO trades
                (address,symbol,entry_price,quantity,invested_usd,status,opened_at)
                VALUES(?,?,?,?,?,'OPEN',?)""",
                (address, token.get("symbol"), price, size / price, size, int(time.time())))
        self.log(f"PAPER BUY {token.get('symbol')} | score {score} | ${size:.2f}")
        return True

    def _cash(self, db):
        start = db.execute("SELECT starting_balance FROM account WHERE id=1").fetchone()[0]
        spent = db.execute("SELECT COALESCE(SUM(invested_usd),0) FROM trades WHERE status='OPEN'").fetchone()[0]
        realized = db.execute("SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='CLOSED'").fetchone()[0]
        return float(start + realized - spent)

    def update_positions(self, prices):
        closed = []
        with self._connect() as db:
            rows = db.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()
            for row in rows:
                price = prices.get(row["address"])
                if not price or price <= 0:
                    continue
                pnl_pct = (float(price) / row["entry_price"] - 1) * 100
                reason = ("STOP_LOSS" if pnl_pct <= -self.stop_loss_pct else
                          "TAKE_PROFIT" if pnl_pct >= self.take_profit_pct else None)
                if reason:
                    pnl = row["quantity"] * float(price) - row["invested_usd"]
                    db.execute("""UPDATE trades SET status='CLOSED',exit_price=?,pnl_usd=?,
                        closed_at=?,exit_reason=? WHERE id=?""",
                        (float(price), pnl, int(time.time()), reason, row["id"]))
                    closed.append((row["symbol"], pnl, reason))
        for symbol, pnl, reason in closed:
            self.log(f"PAPER SELL {symbol} | {reason} | P&L ${pnl:.2f}")
        return closed

    def summary(self, prices=None):
        prices = prices or {}
        with self._connect() as db:
            start = float(db.execute("SELECT starting_balance FROM account WHERE id=1").fetchone()[0])
            cash = self._cash(db)
            rows = db.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()
            realized = float(db.execute("SELECT COALESCE(SUM(pnl_usd),0) FROM trades WHERE status='CLOSED'").fetchone()[0])
            unrealized = sum((float(prices.get(r["address"], r["entry_price"])) - r["entry_price"]) * r["quantity"] for r in rows)
            return {"starting_balance": start, "cash": cash,
                    "equity": cash + sum(r["invested_usd"] for r in rows) + unrealized,
                    "realized_pnl": realized, "unrealized_pnl": unrealized,
                    "open_positions": len(rows), "positions": [dict(r) for r in rows]}

    def recent_trades(self, limit=100):
        with self._connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (int(limit),))]
    def recent_snapshots(self, limit=100):
        with self._connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM snapshots ORDER BY id DESC LIMIT ?", (int(limit),))]
    def recent_events(self, limit=100):
        with self._connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (int(limit),))]
