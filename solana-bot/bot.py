"""Continuous Solana market scanner + PAPER trading loop. Live trading is intentionally absent."""
import asyncio
import os
import signal
from dotenv import load_dotenv
from scanner.dexscreener import DexScreener
from intelligence.scoring import score_token
from risk.onchain import OnChainSecurity
from trading.paper import PaperBroker

load_dotenv()
INTERVAL = max(20, int(os.getenv("SCAN_INTERVAL_SECONDS", "60")))
MIN_AGE = max(1, int(os.getenv("PAPER_MAX_TOKEN_AGE_MINUTES", "1440")))


def eligible_age(token):
    created = token.get("created_at")
    if not created:
        return False
    import time
    age_minutes = max(0, (time.time() * 1000 - float(created)) / 60000)
    return age_minutes <= MIN_AGE


async def run():
    broker = PaperBroker(
        starting_balance=float(os.getenv("PAPER_START_BALANCE_USD", "1000")),
        trade_size=float(os.getenv("PAPER_TRADE_SIZE_USD", "25")),
        max_positions=int(os.getenv("PAPER_MAX_OPEN_POSITIONS", "5")),
        stop_loss_pct=float(os.getenv("PAPER_STOP_LOSS_PCT", "20")),
        take_profit_pct=float(os.getenv("PAPER_TAKE_PROFIT_PCT", "40")),
    )
    scanner = DexScreener()
    security = OnChainSecurity()
    await scanner.start()
    broker.log("Bot started in PAPER mode. No real transactions can be sent.")
    try:
        while True:
            try:
                tokens = await scanner.scan()
                prices = {t["address"]: float(t.get("price_usd") or 0) for t in tokens}
                open_positions = broker.summary()["positions"]
                held_addresses = [position["address"] for position in open_positions]
                held_prices = await scanner.fetch_token_prices(held_addresses)
                prices.update(held_prices)
                broker.update_positions(prices)
                checked = 0
                for token in tokens:
                    score = score_token(token)
                    broker.record_snapshot(token, score["score"], score["decision"])
                    if score["decision"] != "WATCH" or not eligible_age(token):
                        continue
                    checked += 1
                    # Expensive on-chain checks are reserved for top candidates.
                    if checked > 8:
                        break
                    result = await security.check_mint(token["address"])
                    if result.get("status") != "PARSED":
                        broker.log(f"REVIEW {token.get('symbol')}: mint data not parsed", "WARNING")
                        continue
                    if result.get("risks"):
                        broker.log(f"REJECT {token.get('symbol')}: " + "; ".join(result["risks"]), "WARNING")
                        continue
                    broker.open_position(token, score["score"])
                summary = broker.summary(prices)
                print(f"Scanned {len(tokens)} pairs | paper equity ${summary['equity']:.2f} | "
                      f"open {summary['open_positions']} | realized P&L ${summary['realized_pnl']:.2f}")
            except Exception as exc:
                broker.log(f"Scan cycle failed: {type(exc).__name__}: {exc}", "ERROR")
                print("Scan cycle error:", exc)
            await asyncio.sleep(INTERVAL)
    finally:
        await scanner.close()
        broker.log("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Stopped.")
