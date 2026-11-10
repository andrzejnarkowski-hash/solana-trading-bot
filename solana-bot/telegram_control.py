"""Telegram read-only control panel for the paper-trading bot.

Only explicitly allowlisted Telegram user IDs can inspect bot data. /start is
available to show a user's numeric ID during setup. No live trading commands.
"""
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)


class TelegramControl:
    def __init__(self, token, allowed_user_ids, broker):
        self.token = (token or "").strip()
        self.allowed_user_ids = {
            int(value.strip()) for value in (allowed_user_ids or "").split(",")
            if value.strip().isdigit()
        }
        self.broker = broker
        self.application = None

    @property
    def enabled(self):
        return bool(self.token)

    async def start(self):
        if not self.enabled:
            self.broker.log(
                "Telegram disabled: configure TELEGRAM_BOT_TOKEN locally to enable it.",
                "WARNING",
            )
            return False
        self.application = Application.builder().token(self.token).build()
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("positions", self.positions_command))
        self.application.add_handler(CommandHandler("trades", self.trades_command))
        self.application.add_handler(CommandHandler("events", self.events_command))
        await self.application.initialize()
        await self.application.start()
        if self.application.updater is None:
            raise RuntimeError("Telegram polling updater is unavailable")
        await self.application.updater.start_polling(drop_pending_updates=True)
        if self.allowed_user_ids:
            self.broker.log("Telegram control panel started (allowlisted users only).")
        else:
            self.broker.log(
                "Telegram started in onboarding mode: send /start to get your user ID, "
                "then add it to TELEGRAM_ALLOWED_USER_IDS.",
                "WARNING",
            )
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

    async def _authorized(self, update: Update):
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return False
        if chat.type != "private":
            await update.effective_message.reply_text("Use me in a private chat.")
            return False
        if user.id not in self.allowed_user_ids:
            await update.effective_message.reply_text(
                f"Not authorized. Your Telegram user ID is: {user.id}\n"
                "Add this ID to TELEGRAM_ALLOWED_USER_IDS in your private .env, "
                "then restart the bot."
            )
            return False
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return
        if user.id not in self.allowed_user_ids:
            await update.effective_message.reply_text(
                f"Your Telegram user ID: {user.id}\n"
                "Add it to TELEGRAM_ALLOWED_USER_IDS in your private .env, then restart."
            )
            return
        await update.effective_message.reply_text(
            "Paper-trading bot connected. Send /help to see available commands."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._authorized(update):
            return
        await update.effective_message.reply_text(
            "Available commands (paper mode only):\n"
            "/status — balance and performance\n"
            "/positions — current paper positions\n"
            "/trades — latest paper trades\n"
            "/events — latest bot log events\n"
            "/help — this message\n\n"
            "Telegram cannot execute live trades."
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._authorized(update):
            return
        summary = self.broker.summary()
        performance = self.broker.performance()
        await update.effective_message.reply_text(
            "PAPER BOT STATUS\n"
            f"Equity: ${summary['equity']:.2f}\n"
            f"Cash: ${summary['cash']:.2f}\n"
            f"Realized P&L: ${summary['realized_pnl']:.2f}\n"
            f"Unrealized P&L: ${summary['unrealized_pnl']:.2f}\n"
            f"Open positions: {summary['open_positions']}\n"
            f"Closed trades: {performance['closed_trades']}\n"
            f"Win rate: {performance['win_rate_pct']:.2f}%"
        )

    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._authorized(update):
            return
        positions = self.broker.summary()["positions"]
        if not positions:
            await update.effective_message.reply_text("No open paper positions.")
            return
        lines = ["OPEN PAPER POSITIONS"]
        for position in positions[:15]:
            lines.append(
                f"{position.get('symbol') or 'UNKNOWN'} | "
                f"net P&L ${position['unrealized_pnl_usd']:.2f} "
                f"({position['unrealized_pnl_pct']:.2f}%)\n"
                f"CA: {position['address']}"
            )
        await update.effective_message.reply_text("\n\n".join(lines)[:4000])

    async def trades_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._authorized(update):
            return
        trades = self.broker.recent_trades(10)
        if not trades:
            await update.effective_message.reply_text("No paper trades recorded yet.")
            return
        lines = ["LATEST PAPER TRADES"]
        for trade in trades:
            pnl = trade.get("pnl_usd")
            result = f"${pnl:.2f}" if pnl is not None else "OPEN"
            lines.append(
                f"{trade.get('symbol') or 'UNKNOWN'} | {trade['status']} | {result}"
            )
        await update.effective_message.reply_text("\n".join(lines))

    async def events_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._authorized(update):
            return
        events = self.broker.recent_events(10)
        if not events:
            await update.effective_message.reply_text("No bot events recorded yet.")
            return
        lines = ["LATEST BOT EVENTS"]
        for event in events:
            lines.append(f"[{event['level']}] {event['message'][:220]}")
        await update.effective_message.reply_text("\n".join(lines)[:4000])
