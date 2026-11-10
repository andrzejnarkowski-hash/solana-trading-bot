"""Private Telegram command center for the Solana paper trader.

Remote controls can pause/resume NEW PAPER ENTRIES only. Scanning and simulated
position exit management continue while paused. No live transaction execution.
"""
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


class TelegramControl:
    def __init__(self, token, allowed_user_ids, broker, trading_enabled=None):
        self.token = (token or "").strip()
        self.allowed_user_ids = {
            int(value.strip()) for value in (allowed_user_ids or "").split(",")
            if value.strip().isdigit()
        }
        self.broker = broker
        self.trading_enabled = trading_enabled
        self.application = None
        self.menu = ReplyKeyboardMarkup(
            [["▶️ RUN / Start buying", "⏹ STOP buying"],
             ["📊 Status", "🔎 Top signals"],
             ["💼 Positions", "📈 Performance"],
             ["🧾 Trades", "🛡 Risk settings"],
             ["📡 Events", "❔ Help"]],
            resize_keyboard=True,
        )

    @property
    def enabled(self):
        return bool(self.token)

    def _entries_enabled(self):
        return self.trading_enabled is None or self.trading_enabled.is_set()

    async def start(self):
        if not self.enabled:
            self.broker.log("Telegram disabled: TELEGRAM_BOT_TOKEN is missing.", "WARNING")
            return False
        self.application = Application.builder().token(self.token).build()
        handlers = {
            "start": self.start_command, "help": self.help_command,
            "run": self.resume_command, "stop": self.pause_command,
            "setsize": self.setsize_command, "size": self.setsize_command,
            "status": self.status_command, "positions": self.positions_command,
            "trades": self.trades_command, "events": self.events_command,
            "pause": self.pause_command, "resume": self.resume_command,
            "top": self.top_command, "performance": self.performance_command,
            "risk": self.risk_command,
        }
        for command, callback in handlers.items():
            self.application.add_handler(CommandHandler(command, callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.menu_command))
        await self.application.initialize()
        await self.application.start()
        if self.application.updater is None:
            raise RuntimeError("Telegram polling updater is unavailable")
        await self.application.updater.start_polling(drop_pending_updates=True)
        self.broker.log("Telegram command center started (allowlisted users only).")
        return True

    async def stop(self):
        if not self.application:
            return
        if self.application.updater and self.application.updater.running:
            await self.application.updater.stop()
        if self.application.running:
            await self.application.stop()
        await self.application.shutdown()
        self.application = None

    async def _authorized(self, update):
        user, chat = update.effective_user, update.effective_chat
        if not user or not chat:
            return False
        if chat.type != "private":
            await update.effective_message.reply_text("Use me in a private chat.")
            return False
        if user.id not in self.allowed_user_ids:
            await update.effective_message.reply_text(f"Not authorized. Your Telegram ID: {user.id}")
            return False
        return True

    async def start_command(self, update, context):
        user = update.effective_user
        if not user:
            return
        if user.id not in self.allowed_user_ids:
            await update.effective_message.reply_text(
                f"Your Telegram user ID: {user.id}\nAdd it to TELEGRAM_ALLOWED_USER_IDS and restart."
            )
            return
        await update.effective_message.reply_text(
            "🟢 SOLANA PAPER BOT CONNECTED\nChoose an action below. Live trading is not implemented.",
            reply_markup=self.menu,
        )

    async def menu_command(self, update, context):
        if not await self._authorized(update):
            return
        actions = {
            "▶️ RUN / Start buying": self.resume_command,
            "⏹ STOP buying": self.pause_command,
            "📊 Status": self.status_command,
            "🔎 Top signals": self.top_command,
            "💼 Positions": self.positions_command,
            "📈 Performance": self.performance_command,
            "🧾 Trades": self.trades_command,
            "🛡 Risk settings": self.risk_command,
            "📡 Events": self.events_command,
            "❔ Help": self.help_command,
        }
        callback = actions.get((update.effective_message.text or "").strip())
        if callback:
            await callback(update, context)

    async def help_command(self, update, context):
        if await self._authorized(update):
            await update.effective_message.reply_text(
                "SOLANA PAPER BOT CONTROL\n"
                "/run — start allowing new paper buys\n"
                "/stop — stop new buys; open positions are still monitored\n"
                "/setsize 20 — set each new paper position to $20 (range $1–$1,000)\n"
                "/status — equity, cash and P&L\n/top — best saved scanner signals\n"
                "/positions — open positions\n/performance — closed-trade statistics\n"
                "/trades — recent trades\n/risk — configured limits\n/events — recent logs\n"
                "No command can send real transactions.",
                reply_markup=self.menu,
            )

    async def pause_command(self, update, context):
        if not await self._authorized(update):
            return
        if self.trading_enabled is not None:
            self.trading_enabled.clear()
        self.broker.set_entries_enabled(False)
        await update.effective_message.reply_text(
            "⏹ STOPPED: no new paper buys. Scanner and open-position monitoring stay ON.",
            reply_markup=self.menu,
        )

    async def resume_command(self, update, context):
        if not await self._authorized(update):
            return
        if self.trading_enabled is not None:
            self.trading_enabled.set()
        self.broker.set_entries_enabled(True)
        await update.effective_message.reply_text(
            "▶️ RUNNING: new paper buys are enabled. The scanner keeps running continuously.",
            reply_markup=self.menu,
        )

    async def setsize_command(self, update, context):
        if not await self._authorized(update):
            return
        if len(context.args) != 1:
            await update.effective_message.reply_text(
                "Send the amount after the command, e.g. /setsize 20"
            )
            return
        try:
            amount = float(context.args[0].replace(",", ".").replace("$", ""))
            self.broker.set_trade_size(amount)
        except (TypeError, ValueError, OverflowError) as exc:
            await update.effective_message.reply_text(
                f"Invalid amount: {exc}\nUse a value from $1 to $1,000."
            )
            return
        await update.effective_message.reply_text(
            f"✅ New trade size: ${self.broker.trade_size:.2f} per token. "
            "This applies to future entries only; open positions do not change.",
            reply_markup=self.menu,
        )

    async def status_command(self, update, context):
        if not await self._authorized(update):
            return
        s, p = self.broker.summary(), self.broker.performance()
        state = "RUNNING" if self._entries_enabled() else "STOPPED (scanner/position monitoring ON)"
        await update.effective_message.reply_text(
            "📊 SOLANA PAPER BOT\n"
            f"Entry engine: {state}\nEquity: ${s['equity']:.2f} "
            f"(start ${s['starting_balance']:.2f})\nCash: ${s['cash']:.2f}\n"
            f"Realized P&L: ${s['realized_pnl']:.2f}\nUnrealized P&L: ${s['unrealized_pnl']:.2f}\n"
            f"Total P&L: ${s['total_pnl']:.2f}\nOpen positions: {s['open_positions']}\n"
            f"Closed trades: {p['closed_trades']} | Win rate: {p['win_rate_pct']:.1f}%\n"
            f"Target per new entry: ${self.broker.trade_size:.2f}",
            reply_markup=self.menu,
        )

    async def positions_command(self, update, context):
        if not await self._authorized(update):
            return
        positions = self.broker.summary()["positions"]
        if not positions:
            await update.effective_message.reply_text("No open paper positions.", reply_markup=self.menu)
            return
        lines = ["💼 OPEN PAPER POSITIONS"]
        for pos in positions[:12]:
            lines.append(
                f"{pos.get('symbol') or 'UNKNOWN'} | P&L ${pos['unrealized_pnl_usd']:.2f} "
                f"({pos['unrealized_pnl_pct']:.2f}%)\nEntry ${pos['entry_price']:.8g} | "
                f"Mark ${pos['market_price_usd']:.8g}\n{pos['address']}"
            )
        await update.effective_message.reply_text("\n\n".join(lines)[:4000], reply_markup=self.menu)

    async def trades_command(self, update, context):
        if not await self._authorized(update):
            return
        trades = self.broker.recent_trades(12)
        if not trades:
            await update.effective_message.reply_text("No paper trades recorded yet.", reply_markup=self.menu)
            return
        lines = ["🧾 RECENT PAPER TRADES"]
        for trade in trades:
            pnl = "OPEN" if trade["pnl_usd"] is None else f"${trade['pnl_usd']:.2f}"
            lines.append(f"{trade.get('symbol') or 'UNKNOWN'} | {trade['status']} | {pnl}")
        await update.effective_message.reply_text("\n".join(lines)[:4000], reply_markup=self.menu)

    async def performance_command(self, update, context):
        if not await self._authorized(update):
            return
        p = self.broker.performance()
        factor = p["profit_factor"] if p["profit_factor"] is not None else "N/A"
        await update.effective_message.reply_text(
            "📈 CLOSED-TRADE PERFORMANCE (PAPER)\n"
            f"Trades: {p['closed_trades']} | Win rate: {p['win_rate_pct']:.2f}%\n"
            f"Profit factor: {factor}\nAverage P&L: ${p['average_pnl_usd']:.2f}\n"
            f"Best: ${p['best_trade_usd']:.2f} | Worst: ${p['worst_trade_usd']:.2f}\n"
            "A small sample is not evidence of a profitable strategy.",
            reply_markup=self.menu,
        )

    async def top_command(self, update, context):
        if not await self._authorized(update):
            return
        snapshots = self.broker.recent_snapshots(500)
        latest = {}
        for item in snapshots:
            address = item.get("address")
            if address and address not in latest and item.get("decision") in ("WATCH", "MONITOR"):
                latest[address] = item
        ranked = sorted(latest.values(), key=lambda x: float(x.get("score") or 0), reverse=True)[:10]
        if not ranked:
            await update.effective_message.reply_text("No qualifying saved signals yet.", reply_markup=self.menu)
            return
        lines = ["🔎 TOP SAVED SCANNER SIGNALS", "Heuristic scores are not buy recommendations."]
        for item in ranked:
            lines.append(
                f"{item.get('symbol') or 'UNKNOWN'} | {item['decision']} | score {float(item.get('score') or 0):.1f}\n"
                f"Liquidity ${float(item.get('liquidity_usd') or 0):,.0f} | "
                f"1h volume ${float(item.get('volume_1h') or 0):,.0f}\n{item['address']}"
            )
        await update.effective_message.reply_text("\n\n".join(lines)[:4000], reply_markup=self.menu)

    async def risk_command(self, update, context):
        if not await self._authorized(update):
            return
        b = self.broker
        await update.effective_message.reply_text(
            "🛡 PAPER RISK SETTINGS (DISPLAY ONLY)\n"
            f"Trade size per new entry: ${b.trade_size:.2f}\nMax positions: {b.max_positions}\n"
            f"Stop loss: {b.stop_loss_pct:.1f}% | Take profit: {b.take_profit_pct:.1f}%\n"
            f"Fee estimate: {b.fee_rate*100:.2f}% each side\n"
            f"Slippage estimate: {b.slippage_rate*100:.2f}% each side\n"
            f"Cooldown: {b.cooldown_seconds//60} min\nDaily loss guard: {b.max_daily_loss_pct:.1f}%\n"
            "Change the entry size anytime with /setsize 20. Existing positions are unchanged.",
            reply_markup=self.menu,
        )

    async def events_command(self, update, context):
        if not await self._authorized(update):
            return
        events = self.broker.recent_events(12)
        if not events:
            await update.effective_message.reply_text("No events recorded yet.", reply_markup=self.menu)
            return
        lines = ["📡 LATEST BOT EVENTS"]
        for event in events:
            lines.append(f"[{event['level']}] {event['message'][:220]}")
        await update.effective_message.reply_text("\n".join(lines)[:4000], reply_markup=self.menu)
