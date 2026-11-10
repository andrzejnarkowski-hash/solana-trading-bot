"""Conservative heuristic market score; fresh pairs use 5-minute activity metrics."""
import math


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def _finite_number(value, default=0.0):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError, OverflowError):
        return default


def score_token(token, min_liquidity=10000, min_volume_1h=5000, min_txns_1h=30, fresh=False):
    liquidity = max(0.0, _finite_number(token.get("liquidity_usd")))

    # A token younger than one minute cannot reasonably satisfy 1h activity
    # thresholds. Use the available 5m metrics for fresh launches.
    if fresh:
        volume = max(0.0, _finite_number(token.get("volume_5m")))
        buys = max(0, int(_finite_number(token.get("buys_5m"))))
        sells = max(0, int(_finite_number(token.get("sells_5m"))))
        change = _finite_number(token.get("price_change_5m"))
        min_volume = 50.0
        min_transactions = 2
    else:
        volume = max(0.0, _finite_number(token.get("volume_1h")))
        buys = max(0, int(_finite_number(token.get("buys_1h"))))
        sells = max(0, int(_finite_number(token.get("sells_1h"))))
        change = _finite_number(token.get("price_change_1h"))
        min_volume = max(0.0, min_volume_1h)
        min_transactions = max(0, int(min_txns_1h))

    transactions = buys + sells
    reasons = []
    if liquidity < max(0.0, min_liquidity):
        reasons.append("Insufficient liquidity")
    if volume < min_volume:
        reasons.append("Insufficient volume")
    if transactions < min_transactions:
        reasons.append("Insufficient trading activity")
    if change < -20:
        reasons.append("Strong negative momentum")
    if reasons:
        return {"score": 0, "decision": "REJECT", "reasons": reasons}

    liquidity_score = clamp(math.log10(max(liquidity, 1) / 1000) * 15, 0, 25)
    volume_score = clamp(math.log10(max(volume, 1) / 50) * (10 if fresh else 12), 0, 20)
    buy_ratio = buys / max(transactions, 1)
    buy_score = clamp((buy_ratio - 0.35) * 40, 0, 20)
    activity_score = clamp(math.log10(max(transactions, 1)) * (15 if fresh else 8), 0, 20 if fresh else 15)
    momentum_score = clamp(10 + change * (0.08 if fresh else 0.15), 0, 10 if fresh else 20)
    pump_penalty = min(30, (change - 80) * 0.3) if change > 80 else 0
    total = round(clamp(liquidity_score + volume_score + buy_score + activity_score + momentum_score - pump_penalty), 2)
    decision = "WATCH" if total >= 75 else "MONITOR" if total >= 55 else "SKIP"
    return {
        "score": total,
        "decision": decision,
        "reasons": [],
        "buy_ratio": round(buy_ratio, 3),
        "pump_penalty": round(pump_penalty, 2),
    }
