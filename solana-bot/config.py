"""Validated environment-backed settings. Secrets belong only in local .env files."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _float(name, default, minimum=0.0):
    try:
        value = float(os.getenv(name, str(default)))
        return value if value >= minimum and value < float("inf") else float(default)
    except (TypeError, ValueError, OverflowError):
        return float(default)


def _int(name, default, minimum=0):
    try:
        value = int(os.getenv(name, str(default)))
        return value if value >= minimum else int(default)
    except (TypeError, ValueError, OverflowError):
        return int(default)


@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv("BOT_MODE", "paper").strip().lower()
    scan_interval_seconds: int = max(20, _int("SCAN_INTERVAL_SECONDS", 60, 20))
    paper_start_balance_usd: float = _float("PAPER_START_BALANCE_USD", 1000, 1)
    paper_trade_size_usd: float = _float("PAPER_TRADE_SIZE_USD", 25, 1)
    paper_max_open_positions: int = max(1, _int("PAPER_MAX_OPEN_POSITIONS", 5, 1))
    paper_stop_loss_pct: float = _float("PAPER_STOP_LOSS_PCT", 20, 0.1)
    paper_take_profit_pct: float = _float("PAPER_TAKE_PROFIT_PCT", 40, 0.1)
    paper_max_token_age_minutes: int = max(1, _int("PAPER_MAX_TOKEN_AGE_MINUTES", 1440, 1))
    min_liquidity_usd: float = _float("MIN_LIQUIDITY_USD", 15000, 0)
    min_volume_1h_usd: float = _float("MIN_VOLUME_1H_USD", 5000, 0)
    min_txns_1h: int = _int("MIN_TXNS_1H", 30, 0)
    paper_fee_bps: float = _float("PAPER_FEE_BPS", 100, 0)
    paper_slippage_bps: float = _float("PAPER_SLIPPAGE_BPS", 150, 0)
    paper_cooldown_minutes: int = _int("PAPER_COOLDOWN_MINUTES", 60, 0)
    paper_max_daily_loss_pct: float = _float("PAPER_MAX_DAILY_LOSS_PCT", 10, 0)
    x_bearer_token: str = os.getenv("X_BEARER_TOKEN", "").strip()
    x_search_query: str = os.getenv("X_SEARCH_QUERY", "solana (CA OR contract OR launched OR pump.fun) -is:retweet lang:en").strip()
    x_poll_interval_seconds: int = max(60, _int("X_POLL_INTERVAL_SECONDS", 300, 60))


settings = Settings()
