import aiohttp
import asyncio
from typing import Any

BASE_URL = "https://api.dexscreener.com"


def _number(value, default=0.0):
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else default
    except (TypeError, ValueError, OverflowError):
        return default


class DexScreener:
    def __init__(self):
        self.session = None

    async def start(self):
        if self.session and not self.session.closed:
            return
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get(self, endpoint: str):
        if not self.session or self.session.closed:
            raise RuntimeError("DexScreener session is not started")
        async with self.session.get(BASE_URL + endpoint) as response:
            response.raise_for_status()
            return await response.json()

    async def discover_tokens(self):
        profiles = await self.get("/token-profiles/latest/v1")
        if not isinstance(profiles, list):
            return []
        addresses = list(dict.fromkeys(
            p["tokenAddress"] for p in profiles
            if isinstance(p, dict) and p.get("chainId") == "solana" and p.get("tokenAddress")
        ))
        tokens = []
        for i in range(0, min(len(addresses), 120), 30):
            try:
                pairs = await self.get("/tokens/v1/solana/" + ",".join(addresses[i:i + 30]))
                if isinstance(pairs, list):
                    tokens.extend(pairs)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
                print(f"DexScreener batch error: {error}")
        return tokens

    def analyze_pair(self, pair: dict[str, Any]):
        base = pair.get("baseToken") or {}
        volume = pair.get("volume") or {}
        txns = pair.get("txns") or {}
        h1, h24 = txns.get("h1") or {}, txns.get("h24") or {}
        changes = pair.get("priceChange") or {}
        return {
            "name": base.get("name"), "symbol": base.get("symbol"),
            "address": base.get("address"), "pair_address": pair.get("pairAddress"),
            "price_usd": _number(pair.get("priceUsd")),
            "liquidity_usd": _number((pair.get("liquidity") or {}).get("usd")),
            "volume_5m": _number(volume.get("m5")), "volume_1h": _number(volume.get("h1")),
            "volume_24h": _number(volume.get("h24")),
            "buys_1h": int(_number(h1.get("buys"))), "sells_1h": int(_number(h1.get("sells"))),
            "buys_24h": int(_number(h24.get("buys"))), "sells_24h": int(_number(h24.get("sells"))),
            "price_change_5m": _number(changes.get("m5")),
            "price_change_1h": _number(changes.get("h1")),
            "market_cap": _number(pair.get("marketCap")),
            "created_at": _number(pair.get("pairCreatedAt")),
            "dex": pair.get("dexId"), "url": pair.get("url"),
        }

    async def fetch_token_prices(self, addresses):
        """Refresh held-token prices independently of the new-token discovery feed."""
        unique = list(dict.fromkeys(a for a in addresses if a))
        prices = {}
        for i in range(0, len(unique), 30):
            batch = unique[i:i + 30]
            try:
                pairs = await self.get("/tokens/v1/solana/" + ",".join(batch))
                for pair in pairs or []:
                    base = pair.get("baseToken") or {}
                    address = base.get("address")
                    price = _number(pair.get("priceUsd"))
                    liquidity = _number((pair.get("liquidity") or {}).get("usd"))
                    current = prices.get(address)
                    if address in batch and price > 0 and (
                        current is None or liquidity > current[1]
                    ):
                        prices[address] = (price, liquidity)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
                print(f"Held-token price refresh error: {error}")
        return {address: item[0] for address, item in prices.items()}

    async def scan(self):
        pairs = await self.discover_tokens()
        best_by_token = {}
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            try:
                token = self.analyze_pair(pair)
                if not token["address"] or token["price_usd"] <= 0:
                    continue
                old = best_by_token.get(token["address"])
                rank = (token["liquidity_usd"], token["volume_1h"])
                old_rank = ((old or {}).get("liquidity_usd", -1), (old or {}).get("volume_1h", -1))
                if old is None or rank > old_rank:
                    best_by_token[token["address"]] = token
            except (ValueError, TypeError, AttributeError, OverflowError):
                continue
        return sorted(best_by_token.values(), key=lambda item: item["volume_1h"], reverse=True)


async def main():
    scanner = DexScreener()
    await scanner.start()
    try:
        tokens = await scanner.scan()
        print(f"Found {len(tokens)} unique Solana tokens.")
        for token in tokens[:15]:
            print(token["symbol"], "price", token["price_usd"], "liquidity", token["liquidity_usd"],
                  "1h volume", token["volume_1h"], "buys/sells",
                  token["buys_1h"], "/", token["sells_1h"], "CA", token["address"])
    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(main())
