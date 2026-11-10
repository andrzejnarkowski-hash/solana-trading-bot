# Solana Meme Scanner & Paper Trader

This project currently runs a continuous DexScreener scanner, a basic market score, on-chain mint-authority checks, a SQLite paper-trading ledger, and a Streamlit dashboard.

## Safety status

**PAPER MODE ONLY.** This version does not contain a live swap executor, does not request a wallet private key, and cannot send real transactions. Do not add private keys to the repository. A later live-trading module must be separately designed, audited, and explicitly enabled; this code is not ready for real funds.

## Setup (Windows / Codespaces)

```bash
cd solana-bot
python -m venv .venv
```
Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python bot.py
```
Linux / Codespaces:
```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

In a second terminal, from `solana-bot/`:
```bash
streamlit run dashboard/app.py
```

Open the local Streamlit URL shown in the terminal.

## Configuration

Edit the values in your local `.env`: paper starting balance, simulated order size, maximum open positions, stop-loss, take-profit, and scan interval. The scanner uses public DexScreener endpoints and the public Solana RPC by default; public endpoints can rate-limit or fail.

## What the score does / does not mean

The score is a heuristic ranking, not a prediction. Mint/freeze authority checks are only a small part of token risk. This version includes a partial top-20 token-account concentration estimate, but it does not identify wallet owners or classify LP/exchange vaults. It does not yet verify LP lock/burn, creator wallet history, insider wallets, transfer simulations, X/Twitter account ownership, post engagement, or image/meme narratives. A parsed mint is not a safe token.

## Current analysis limitations

- Holder concentration is only a partial estimate from the largest 20 token accounts; LP and exchange vaults can distort it. It is logged for review and is not treated as a reliable wallet distribution.
- Social links are metadata only. There is no live X feed, influencer identity verification, engagement analysis, or AI image understanding.
- The paper strategy is intentionally simple and does not model slippage, MEV, priority fees, or failed transactions. Results are not representative of live execution.

## Tests

```bash
python -m unittest discover -v
python -m py_compile bot.py trading/paper.py dashboard/app.py
```
