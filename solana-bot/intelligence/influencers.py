"""Optional manual watchlist.

No account is trusted by default. Add an account only after independently verifying
its identity and history; reputation values are configuration, not measured facts.
"""
INFLUENCERS = {}


def get_influencer(handle):
    handle = (handle or "").lower().strip().lstrip("@")
    if not handle:
        return None
    return INFLUENCERS.get(handle)


def calculate_signal_priority(handle, announcement):
    influencer = get_influencer(handle)
    if not influencer or not influencer.get("enabled", False):
        return {
            "priority": "LOW", "score": 0,
            "reason": "Account is not on the manually configured watchlist",
        }
    reputation = max(0, min(100, float(influencer.get("reputation", 0))))
    confidence = max(0, min(100, float(announcement.get("confidence", 0))))
    score = round(reputation * confidence / 100, 2)
    if announcement.get("signal") == "NEGATIVE":
        score = 0
    priority = "CRITICAL" if score >= 70 else "HIGH" if score >= 35 else "LOW"
    return {
        "priority": priority, "score": score,
        "influencer": influencer.get("handle", handle),
        "reason": "Priority uses a manually configured, unverified reputation value",
    }
