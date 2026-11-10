import asyncio
from scanner.dexscreener import DexScreener
from intelligence.scoring import score_token
from risk.onchain import OnChainSecurity


async def main():
    scanner = DexScreener()
    security = OnChainSecurity()

    await scanner.start()

    try:
        tokens = await scanner.scan()

        candidates = []

        for token in tokens:
            score = score_token(token)

            if score["decision"] == "WATCH":
                candidates.append((token, score))

        for token, score in candidates[:5]:
            print("\n" + "=" * 50)
            print(token["symbol"], score["score"])

            result = await security.check_mint(token["address"])

            print("SECURITY:", result)

    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(main())
