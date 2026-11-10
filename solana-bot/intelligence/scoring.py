"""Heuristic market score. It ranks candidates; it does not predict returns."""
import math


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def _finite_number(value, default=0.0):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError, OverflowError):
        return default


def score_token(token):
    liquidity = max(0.0, _finite_number(token.get("liquidity_usd")))
    volume = max(0.0, _finite_number(token.get("volume_1h")))
    buys = max(0, int(_finite_number(token.get("buys_1h"))))
    sells = max(0, int(_finite_number(token.get("sells_1h"))))
    change = _finite_number(token.get("price_change_1h"))
    transactions = buys + sells
    reasons = []
    if liquidity < 10000:
        reasons.append("Insufficient liquidity")
    if volume < 5000:
        reasons.append("Insufficient volume")
    if transactions < 30:
        reasons.append("Insufficient trading activity")
    if change < -20:
        reasons.append("Strong negative momentum")
    if reasons:
        return {"score": 0, "decision": "REJECT", "reasons": reasons}
    liquidity_score = clamp(math.log10(max(liquidity, 1) / 1000) * 15, 0, 25)
    volume_score = clamp(math.log10(max(volume, 1) / 1000) * 12, 0, 20)
    buy_ratio = buys / max(transactions, 1)
    buy_score = clamp((buy_ratio - 0.35) * 40, 0, 20)
    activity_score = clamp(math.log10(max(transactions, 1)) * 8, 0, 15)
    momentum_score = clamp(10 + change * 0.15, 0, 20)
    pump_penalty = min(30, (change - 80) * 0.3) if change > 80 else 0
    total = round(clamp(liquidity_score + volume_score + buy_score +
                        activity_score + momentum_score - pump_penalty), 2)
    decision = "WATCH" if total >= 75 else "MONITOR" if total >= 55 else "SKIP"
    return {"score": total, "decision": decision, "reasons": [],
            "buy_ratio": round(buy_ratio, 3), "pump_penalty": round(pump_penalty, 2)}
