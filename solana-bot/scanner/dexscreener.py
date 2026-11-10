import aiohttp
import asyncio
from typing import Any

BASE_URL = "https://api.dexscreener.com"


class DexScreener:
    def __init__(self):
        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        )

    async def close(self):
        if self.session:
            await self.session.close()

    async def get(self, endpoint: str):
        async with self.session.get(BASE_URL + endpoint) as response:
            response.raise_for_status()
            return await response.json()

    async def discover_tokens(self):
        profiles = await self.get("/token-profiles/latest/v1")

        addresses = list(dict.fromkeys(
            p["tokenAddress"]
            for p in profiles
            if p.get("chainId") == "solana"
            and p.get("tokenAddress")
        ))

        tokens = []

        for i in range(0, min(len(addresses), 120), 30):
            batch = addresses[i:i + 30]
            endpoint = "/tokens/v1/solana/" + ",".join(batch)

            try:
                pairs = await self.get(endpoint)
                tokens.extend(pairs or [])
            except Exception as error:
                print(f"Batch error: {error}")

        return tokens

    def analyze_pair(self, pair: dict[str, Any]):
        liquidity = (pair.get("liquidity") or {}).get("usd") or 0
        volume = pair.get("volume") or {}
        transactions = pair.get("txns") or {}
        h1 = transactions.get("h1") or {}
        h24 = transactions.get("h24") or {}
        changes = pair.get("priceChange") or {}

        buys = h1.get("buys", 0)
        sells = h1.get("sells", 0)

        return {
            "name": pair.get("baseToken", {}).get("name"),
            "symbol": pair.get("baseToken", {}).get("symbol"),
            "address": pair.get("baseToken", {}).get("address"),
            "pair_address": pair.get("pairAddress"),
            "price_usd": float(pair.get("priceUsd") or 0),
            "liquidity_usd": liquidity,
            "volume_5m": volume.get("m5", 0),
            "volume_1h": volume.get("h1", 0),
            "volume_24h": volume.get("h24", 0),
            "buys_1h": buys,
            "sells_1h": sells,
            "buys_24h": h24.get("buys", 0),
            "sells_24h": h24.get("sells", 0),
            "price_change_5m": changes.get("m5", 0),
            "price_change_1h": changes.get("h1", 0),
            "market_cap": pair.get("marketCap"),
            "created_at": pair.get("pairCreatedAt"),
            "dex": pair.get("dexId"),
            "url": pair.get("url"),
        }

    async def scan(self):
        pairs = await self.discover_tokens()
        results = []

        for pair in pairs:
            try:
                token = self.analyze_pair(pair)
                if token["address"] and token["price_usd"] > 0:
                    results.append(token)
            except (ValueError, TypeError, AttributeError):
                continue

        results.sort(
            key=lambda x: x["volume_1h"],
            reverse=True
        )

        return results


async def main():
    scanner = DexScreener()
    await scanner.start()

    try:
        print("\nSCANNING SOLANA MEMECOINS...\n")
        tokens = await scanner.scan()

        print(f"Found {len(tokens)} trading pairs.\n")

        for token in tokens[:15]:
            print("=" * 50)
            print(f"{token['name']} ({token['symbol']})")
            print(f"Price: ${token['price_usd']}")
            print(f"Liquidity: ${token['liquidity_usd']:,.2f}")
            print(f"1H Volume: ${token['volume_1h']:,.2f}")
            print(
                f"1H Buys/Sells: "
                f"{token['buys_1h']}/{token['sells_1h']}"
            )
            print(f"1H Change: {token['price_change_1h']}%")
            print(f"Address: {token['address']}")
            print(f"Chart: {token['url']}")

    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(main())
