import asyncio

from scanner.dexscreener import DexScreener
from intelligence.evaluator import CombinedEvaluator


async def main():
    scanner = DexScreener()
    evaluator = CombinedEvaluator()

    await scanner.start()

    try:
        tokens = await scanner.scan()

        for token in tokens[:10]:
            result = await evaluator.evaluate(token)

            print("\n" + "=" * 50)
            print("TOKEN:", result["symbol"])
            print("ADDRESS:", token["address"])
            print("MARKET SCORE:", result["market_score"])
            print("MARKET DECISION:", result["market_decision"])
            print("SECURITY:", result["security"])
            print("SOCIAL:", result["social"])
            print("FINAL DECISION:", result["final_decision"])

    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(main())
