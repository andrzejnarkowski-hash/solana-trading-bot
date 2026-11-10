import asyncio
from scanner.dexscreener import DexScreener
from intelligence.scoring import score_token
from intelligence.social import SocialIntelligence


async def main():
    scanner = DexScreener()
    social = SocialIntelligence()

    await scanner.start()

    try:
        tokens = await scanner.scan()

        candidates = []

        for token in tokens:
            result = score_token(token)

            if result["decision"] == "WATCH":
                candidates.append(token)

        for token in candidates[:5]:
            print("\n" + "=" * 50)
            print("TOKEN:", token["symbol"])

            result = await social.analyze(token)

            print("SOCIAL INTELLIGENCE:", result)

    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(main())
