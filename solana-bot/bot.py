"""Continuous Solana scanner + conservative PAPER trading loop. No live execution."""
import asyncio
import time

from config import settings
from scanner.dexscreener import DexScreener
from intelligence.scoring import score_token
from risk.onchain import OnChainSecurity
from risk.holders import HolderConcentration
from intelligence.social import SocialIntelligence
from trading.paper import PaperBroker
from intelligence.x_monitor import XMonitor
from intelligence.ca_detector import extract_addresses
from intelligence.announcement import analyze_announcement
from intelligence.influencers import calculate_signal_priority
from telegram_control import TelegramControl

INTERVAL = settings.scan_interval_seconds
MIN_AGE = settings.paper_max_token_age_minutes
PAPER_ENTRY_INTERVAL = settings.paper_entry_interval_seconds


def eligible_age(token, now_ms=None):
    created = token.get("created_at")
    try:
        created = float(created)
    except (TypeError, ValueError, OverflowError):
        return False
    if created <= 0:
        return False
    now_ms = now_ms if now_ms is not None else time.time() * 1000
    age_minutes = max(0, (now_ms - created) / 60000)
    return age_minutes <= MIN_AGE


async def run():
    # This build intentionally refuses to start any mode other than paper.
    if settings.mode != "paper":
        raise RuntimeError("Only BOT_MODE=paper is supported. Live execution is not implemented.")
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
    scanner = DexScreener()
    security = OnChainSecurity()
    holders = HolderConcentration()
    social = SocialIntelligence()
    x_monitor = XMonitor(
        bearer_token=settings.x_bearer_token,
        query=settings.x_search_query,
        poll_interval_seconds=settings.x_poll_interval_seconds,
    )
    x_disabled_logged = False
    last_aggressive_entry = 0.0
    trading_enabled = asyncio.Event()
    # PAPER mode starts with entries enabled so the bot trades immediately.
    # Telegram /stop can pause new entries without stopping scanning or exits.
    broker.set_entries_enabled(True)
    trading_enabled.set()
    telegram = TelegramControl(
        token=settings.telegram_bot_token,
        allowed_user_ids=settings.telegram_allowed_user_ids,
        broker=broker,
        trading_enabled=trading_enabled,
    )
    await scanner.start()
    broker.log(
        "Bot started in PAPER mode. Estimated fees/slippage are applied; no real transactions can be sent."
    )
    try:
        try:
            await telegram.start()
        except Exception as exc:
            broker.log(f"Telegram startup failed: {type(exc).__name__}: {exc}", "WARNING")
        while True:
            try:
                x_result = await x_monitor.poll()
                if x_result["status"] == "DISABLED" and not x_disabled_logged:
                    broker.log(
                        "X monitoring disabled: configure X_BEARER_TOKEN locally to enable official X API search.",
                        "WARNING",
                    )
                    x_disabled_logged = True
                elif x_result["status"] == "ERROR":
                    broker.log("X API poll failed: " + x_result.get("reason", "unknown error"), "WARNING")
                elif x_result["status"] == "OK":
                    for post in x_result["posts"]:
                        addresses = extract_addresses(post["text"])
                        if not addresses:
                            continue
                        announcement = analyze_announcement(post["text"], addresses)
                        priority = calculate_signal_priority(post["username"], announcement)
                        broker.log(
                            f"X CA MENTION @{post['username']} | {announcement['signal']} | "
                            f"priority {priority['priority']} | followers {post['followers_count']} | "
                            f"likes {post['like_count']} | CAs {', '.join(addresses)} | "
                            "not an endorsement or buy signal",
                            "INFO",
                        )
                tokens = await scanner.scan()
                prices = {t["address"]: float(t.get("price_usd") or 0) for t in tokens}
                open_positions = broker.summary()["positions"]
                held_addresses = [position["address"] for position in open_positions]
                prices.update(await scanner.fetch_token_prices(held_addresses))
                closed = broker.update_positions(prices)
                for symbol, pnl, reason in closed:
                    print(f"Closed {symbol}: {reason}, net P&L ${pnl:.2f}")

                checked = 0
                now = time.time()
                aggressive_window = (
                    settings.paper_aggressive_mode
                    and trading_enabled.is_set()
                    and now - last_aggressive_entry >= PAPER_ENTRY_INTERVAL
                )
                fresh_candidates = []
                for token in tokens:
                    is_fresh = eligible_age(token)
                    score = score_token(
                        token,
                        min_liquidity=settings.min_liquidity_usd,
                        min_volume_1h=settings.min_volume_1h_usd,
                        min_txns_1h=settings.min_txns_1h,
                        fresh=is_fresh,
                    )
                    broker.record_snapshot(token, score["score"], score["decision"])
                    if is_fresh:
                        fresh_candidates.append((token, score))

                # Aggressive PAPER mode takes one fresh candidate roughly every 90 seconds.
                # It still requires basic mint-risk checks and never sends a real trade.
                if aggressive_window and fresh_candidates:
                    fresh_candidates.sort(
                        key=lambda item: (
                            item[1]["score"],
                            item[0].get("liquidity_usd", 0),
                            item[0].get("volume_5m", 0),
                        ),
                        reverse=True,
                    )
                    for token, score in fresh_candidates:
                        if checked >= 8:
                            break
                        checked += 1
                        result = await security.check_mint(token["address"])
                        if result.get("status") != "PARSED":
                            broker.log(f"REVIEW {token.get('symbol')}: mint data not parsed", "WARNING")
                            continue
                        if result.get("risks"):
                            broker.log(
                                f"REJECT {token.get('symbol')}: " + "; ".join(result["risks"]),
                                "WARNING",
                            )
                            continue

                        holder_result = await holders.analyze(token["address"])
                        if holder_result.get("status") == "PARTIAL":
                            broker.log(
                                f"HOLDER ESTIMATE {token.get('symbol')}: top20 wallet owners "
                                f"{holder_result['top20_wallet_share_pct']}% of supply; "
                                "LP/exchange/program vaults are not classified",
                                "WARNING",
                            )

                        social_result = await social.analyze(token)
                        if social_result.get("warnings"):
                            broker.log(
                                f"SOCIAL REVIEW {token.get('symbol')}: " +
                                "; ".join(social_result["warnings"]), "INFO"
                            )

                        opened = broker.open_position(token, score["score"])
                        if opened:
                            last_aggressive_entry = now
                            print(
                                f"Paper entry: {token.get('symbol')} "
                                f"score={score['score']} aggressive_paper=true"
                            )
                            break

                summary = broker.summary(prices)
                print(
                    f"Scanned {len(tokens)} tokens | paper equity ${summary['equity']:.2f} | "
                    f"cash ${summary['cash']:.2f} | open {summary['open_positions']} | "
                    f"realized P&L ${summary['realized_pnl']:.2f}"
                )
            except Exception as exc:
                broker.log(f"Scan cycle failed: {type(exc).__name__}: {exc}", "ERROR")
                print("Scan cycle error:", exc)
            await asyncio.sleep(INTERVAL)
    finally:
        try:
            await telegram.stop()
        except Exception as exc:
            broker.log(f"Telegram shutdown warning: {type(exc).__name__}: {exc}", "WARNING")
        await scanner.close()
        broker.log("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Stopped.")
