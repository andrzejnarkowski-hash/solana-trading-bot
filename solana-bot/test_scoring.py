import asyncio
from scanner.dexscreener import DexScreener
from intelligence.scoring import score_token


async def main():
    scanner = DexScreener()
    await scanner.start()

    try:
        tokens = await scanner.scan()

        ranked = []

        for token in tokens:
            result = score_token(token)
            ranked.append((token, result))

        ranked.sort(
            key=lambda item: item[1]["score"],
            reverse=True
        )

        print("\n========== BOT INTELLIGENCE ==========\n")

        for token, result in ranked:
            print(
                f"{token['symbol']:<15} "
                f"SCORE: {result['score']:>6}/100 "
                f"DECISION: {result['decision']}"
            )

            if result["reasons"]:
                print("  Reasons:", ", ".join(result["reasons"]))

    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(main())
