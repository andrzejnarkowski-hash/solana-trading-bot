import asyncio

from intelligence.ca_detector import extract_addresses
from intelligence.announcement import analyze_announcement
from intelligence.influencers import calculate_signal_priority
from risk.onchain import OnChainSecurity


async def analyze_post(author, text):
    addresses = extract_addresses(text)
    announcement = analyze_announcement(text, addresses)
    priority = calculate_signal_priority(author, announcement)

    security_checker = OnChainSecurity()
    verified_tokens = []

    for address in addresses:
        security = await security_checker.check_mint(address)

        verified = security.get("status") == "PARSED"

        verified_tokens.append({
            "address": address,
            "is_valid_mint": verified,
            "security": security,
        })

    return {
        "author": author,
        "announcement": announcement,
        "priority": priority,
        "verified_tokens": verified_tokens,
        "auto_buy": False,
    }


async def main():
    post = (
        "I just launched my coin! Official CA: "
        "DigVnUDwgbSSWNMNsgzGNw8EQhqwjniPU2EsfD4Wpump"
    )

    result = await analyze_post("ansem", post)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
