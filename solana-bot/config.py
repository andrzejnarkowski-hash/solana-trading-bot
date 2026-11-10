"""Environment-backed configuration. Keep secrets out of Git."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv("BOT_MODE", "paper").lower()
    scan_interval_seconds: int = max(20, int(os.getenv("SCAN_INTERVAL_SECONDS", "60")))
    paper_start_balance_usd: float = float(os.getenv("PAPER_START_BALANCE_USD", "1000"))
    paper_trade_size_usd: float = float(os.getenv("PAPER_TRADE_SIZE_USD", "25"))
    paper_max_open_positions: int = max(1, int(os.getenv("PAPER_MAX_OPEN_POSITIONS", "5")))
    paper_stop_loss_pct: float = float(os.getenv("PAPER_STOP_LOSS_PCT", "20"))
    paper_take_profit_pct: float = float(os.getenv("PAPER_TAKE_PROFIT_PCT", "40"))
    paper_max_token_age_minutes: int = max(1, int(os.getenv("PAPER_MAX_TOKEN_AGE_MINUTES", "1440")))
    min_liquidity_usd: float = float(os.getenv("MIN_LIQUIDITY_USD", "15000"))
    min_volume_1h_usd: float = float(os.getenv("MIN_VOLUME_1H_USD", "5000"))
    min_txns_1h: int = int(os.getenv("MIN_TXNS_1H", "30"))

settings = Settings()
