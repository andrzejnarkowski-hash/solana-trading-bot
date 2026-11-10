INFLUENCERS = {
    "ansem": {
        "handle": "ansem",
        "reputation": 95,
        "tier": "TOP",
        "enabled": True,
    },
}


def get_influencer(handle):
    handle = (handle or "").lower().strip().lstrip("@")

    if not handle:
        return None

    return INFLUENCERS.get(handle)


def calculate_signal_priority(handle, announcement):
    influencer = get_influencer(handle)

    if not influencer or not influencer["enabled"]:
        return {
            "priority": "LOW",
            "score": 0,
            "reason": "Account is not on the trusted list",
        }

    reputation = influencer["reputation"]
    confidence = announcement.get("confidence", 0)

    score = round(reputation * confidence / 100, 2)

    if announcement.get("signal") == "NEGATIVE":
        score = 0

    if score >= 70:
        priority = "CRITICAL"
    elif score >= 35:
        priority = "HIGH"
    else:
        priority = "LOW"

    return {
        "priority": priority,
        "score": score,
        "influencer": influencer["handle"],
        "reason": "Priority based on configured account reputation and signal",
    }


if __name__ == "__main__":
    test_signal = {
        "signal": "POSSIBLE_LAUNCH",
        "confidence": 60,
    }

    print(calculate_signal_priority("ansem", test_signal))
