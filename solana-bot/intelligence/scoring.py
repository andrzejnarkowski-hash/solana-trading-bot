import math


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def score_token(token):
    liquidity = float(token.get("liquidity_usd") or 0)
    volume = float(token.get("volume_1h") or 0)
    buys = int(token.get("buys_1h") or 0)
    sells = int(token.get("sells_1h") or 0)
    change = float(token.get("price_change_1h") or 0)

    transactions = buys + sells

    # Hard safety filters
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
        return {
            "score": 0,
            "decision": "REJECT",
            "reasons": reasons,
        }

    # Liquidity score: maximum 25
    liquidity_score = clamp(
        math.log10(max(liquidity, 1) / 1000) * 15,
        0, 25
    )

    # Volume score: maximum 20
    volume_score = clamp(
        math.log10(max(volume, 1) / 1000) * 12,
        0, 20
    )

    # Buy pressure: maximum 20
    buy_ratio = buys / max(transactions, 1)
    buy_score = clamp((buy_ratio - 0.35) * 40, 0, 20)

    # Trading activity: maximum 15
    activity_score = clamp(
        math.log10(max(transactions, 1)) * 8,
        0, 15
    )

    # Momentum: maximum 20
    momentum_score = clamp(
        10 + change * 0.15,
        0, 20
    )

    # Extreme pump penalty
    pump_penalty = 0

    if change > 80:
        pump_penalty = min(30, (change - 80) * 0.3)

    total = round(clamp(
        liquidity_score
        + volume_score
        + buy_score
        + activity_score
        + momentum_score
        - pump_penalty
    ), 2)

    if total >= 75:
        decision = "WATCH"
    elif total >= 55:
        decision = "MONITOR"
    else:
        decision = "SKIP"

    return {
        "score": total,
        "decision": decision,
        "reasons": [],
        "buy_ratio": round(buy_ratio, 3),
        "pump_penalty": round(pump_penalty, 2),
    }
