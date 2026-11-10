# Solana Meme Scanner & Paper Trader

A research prototype for scanning Solana token markets, applying conservative filters, tracking paper positions, and reviewing recorded signals. It is **paper-only**.

## Safety first

**No live swap executor exists.** This application does not connect a wallet, request a seed phrase/private key, sign transactions, or send trades. `BOT_MODE` must be `paper`; other values are rejected at startup. Never paste wallet secrets into GitHub, Codespaces, or ChatGPT.

A token passing these checks is not necessarily safe. Mint authority checks, token-account concentration, and self-reported social links each have important blind spots.

## What it currently does

- Discovers recent Solana token profiles through the public DexScreener API and normalizes/deduplicates pairs.
- Scores market liquidity, one-hour volume, buy/sell activity and momentum using configurable minimum thresholds.
- Inspects SPL Token and Token-2022 mint authorities and selected extensions.
- Estimates concentration in the largest 20 token accounts (not unique holders).
- Collects self-reported social metadata as review context only; links do not establish legitimacy.
- Simulates entries/exits in SQLite with configurable fee and adverse-slippage assumptions, cooldowns, position limits, stop-loss, take-profit and a realized daily-loss guard.
- Provides a Streamlit dashboard with paper performance and a snapshot-based backtest.
- Offers a private Telegram command center with a button menu, pause/resume for new paper entries, top saved signals, performance, risk settings, positions, trades and events. Access is restricted to explicitly allowlisted Telegram user IDs.

## Run in GitHub Codespaces

Open the repository, choose **Code → Codespaces → Create codespace on main**. The devcontainer installs the Python dependencies.

In the terminal:

```bash
cd solana-bot
cp .env.example .env
python -m unittest discover -v
python main.py
```

Open a second terminal for the dashboard:

```bash
cd solana-bot
streamlit run dashboard/app.py --server.address 0.0.0.0
```

Codespaces should forward port 8501. If the bot is running, it records snapshots and paper trades in `solana-bot/data/bot.sqlite3`. The database is local and ignored by Git.

## Windows local setup

```powershell
cd solana-bot
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m unittest discover -v
python main.py
```

Run the dashboard in a second terminal with `streamlit run dashboard/app.py`.

## Configuration

All settings are read from your local `.env` file. Optional X monitoring requires an X API bearer token in `X_BEARER_TOKEN`; leave it blank to keep X monitoring disabled. Never commit the token.

### Telegram setup

1. Message **@BotFather** in Telegram, run `/newbot`, and follow its prompts.
2. Copy the bot token into your private local `.env` as `TELEGRAM_BOT_TOKEN=...`. Do not paste it into chat, source code, or a GitHub commit.
3. Start the application once and open your new bot in Telegram. Send `/start`; it replies with your numeric Telegram user ID.
4. Stop the application, add that ID to `TELEGRAM_ALLOWED_USER_IDS=123456789` in the private `.env`, then restart.
5. Use the Telegram menu or `/help`, `/status`, `/pause`, `/resume`, `/top`, `/positions`, `/performance`, `/risk`, `/trades`, and `/events` in a private chat.

`/pause` disables new paper entries only; scanning and management of existing positions continue. `/resume` allows new simulated entries under configured risk limits. Telegram cannot enable live trading or send blockchain transactions. Risk settings are display-only.

Important paper-execution assumptions:

| Setting | Default | Meaning |
|---|---:|---|
| `PAPER_START_BALANCE_USD` | 1000 | Starting simulated cash |
| `PAPER_TRADE_SIZE_USD` | 25 | Maximum notional per simulated entry |
| `PAPER_MAX_OPEN_POSITIONS` | 5 | Concurrent paper positions |
| `PAPER_STOP_LOSS_PCT` | 20 | Net loss threshold per position |
| `PAPER_TAKE_PROFIT_PCT` | 40 | Net profit threshold per position |
| `PAPER_FEE_BPS` | 100 | Estimated fee on each side (100 bps = 1%) |
| `PAPER_SLIPPAGE_BPS` | 150 | Adverse price movement on each side (150 bps = 1.5%) |
| `PAPER_COOLDOWN_MINUTES` | 60 | Minimum time before re-entering the same mint |
| `PAPER_MAX_DAILY_LOSS_PCT` | 10 | Stops new entries after realized daily losses reach this share of starting balance |
| `MIN_LIQUIDITY_USD` | 15000 | Minimum pool liquidity |
| `MIN_VOLUME_1H_USD` | 5000 | Minimum one-hour volume |
| `MIN_TXNS_1H` | 30 | Minimum one-hour buys plus sells |

Fees and slippage are rough assumptions, not quotes from an exchange or DEX. Actual costs can be much higher for thin, volatile meme coins.

## Backtesting

The dashboard's **Run backtest on saved data** button uses scanner snapshots recorded by the running bot. It delays each signal's entry until the next observation for that mint and charges the configured fee/slippage on entry and exit.

The backtest is deliberately transparent but limited: it cannot reconstruct missing candles, historical liquidity depth, pool changes, MEV, priority fees, failed transactions, or actual executable fills. It is not a substitute for a long forward paper-trading period. A short or incomplete sample is not evidence of a profitable strategy.

## Known limitations — do not mistake these for completed features

- Optional official X API recent-search monitoring is implemented but remains disabled until you provide your own bearer token in local `.env`. It can log public CA mentions and basic engagement counts; it does not verify identity, analyse meme images, or trigger buys. API access, cost and rate limits depend on your X developer account.
- Influencer accounts are not automatically trusted. The default watchlist is empty; any manual reputation value must be independently verified.
- Holder analysis is a partial top-20 token-account estimate. It does not aggregate owners or classify LP, exchange, vesting, and program vaults.
- LP lock/burn verification, creator-wallet history, insider-cluster analysis, honeypot transaction simulation, and robust sellability checks are not implemented.
- Market scoring is heuristic and not a return prediction.
- Public RPC and DexScreener endpoints may rate-limit, return incomplete data, or be unavailable.
- Paper trading is not live trading. Estimated costs and snapshot-based backtesting cannot guarantee realistic execution.

## Tests

```bash
python -m unittest discover -v
python -m py_compile config.py main.py bot.py backtesting.py trading/paper.py dashboard/app.py
```

GitHub Actions runs the test suite and compile checks on relevant pushes and pull requests. A green workflow run should be checked in the repository's **Actions** tab; do not assume a test passed merely because a workflow file exists.
