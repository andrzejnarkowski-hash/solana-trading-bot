import re

LAUNCH_PHRASES = [
    "i launched",
    "just launched",
    "my coin",
    "my token",
    "i created",
    "we launched",
    "official ca",
    "official contract",
    "our token",
]

PROMOTION_PHRASES = [
    "i'm buying",
    "im buying",
    "buying this",
    "i bought",
    "i'm in",
    "im in",
    "bullish on",
    "this is going to send",
]

NEGATIVE_PHRASES = [
    "scam",
    "fake ca",
    "not official",
    "do not buy",
    "don't buy",
    "avoid this",
    "warning",
]


def analyze_announcement(text, addresses):
    text = (text or "").lower()

    if not addresses:
        return {
            "signal": "NO_CA",
            "addresses": [],
            "confidence": 0,
            "reason": "No Solana address detected",
        }

    if any(phrase in text for phrase in NEGATIVE_PHRASES):
        return {
            "signal": "NEGATIVE",
            "addresses": addresses,
            "confidence": 0,
            "reason": "Post contains a warning or negative phrase",
        }

    if any(phrase in text for phrase in LAUNCH_PHRASES):
        return {
            "signal": "POSSIBLE_LAUNCH",
            "addresses": addresses,
            "confidence": 60,
            "reason": "Launch-related language detected; ownership unverified",
        }

    if any(phrase in text for phrase in PROMOTION_PHRASES):
        return {
            "signal": "POSSIBLE_PROMOTION",
            "addresses": addresses,
            "confidence": 40,
            "reason": "Buying or promotional language detected",
        }

    return {
        "signal": "CA_MENTION",
        "addresses": addresses,
        "confidence": 10,
        "reason": "Address mentioned without clear launch or promotion",
    }


if __name__ == "__main__":
    from intelligence.ca_detector import extract_addresses

    post = (
        "I just launched my coin! Official CA: "
        "DigVnUDwgbSSWNMNsgzGNw8EQhqwjniPU2EsfD4Wpump"
    )

    addresses = extract_addresses(post)
    print(analyze_announcement(post, addresses))
