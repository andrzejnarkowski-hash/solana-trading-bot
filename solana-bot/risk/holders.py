"""Partial holder concentration estimate from Solana RPC largest token accounts.

Important: this is token-account concentration, not a complete wallet-holder map.
LP vaults, exchanges, custodians and program-owned accounts can dominate the result.
"""
import aiohttp

RPC_URL = "https://api.mainnet-beta.solana.com"


class HolderConcentration:
    async def _rpc(self, session, method, params):
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        async with session.post(RPC_URL, json=payload) as response:
            response.raise_for_status()
            result = await response.json()
        if result.get("error"):
            raise RuntimeError(str(result["error"]))
        return result.get("result")

    async def analyze(self, mint):
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                largest, supply = await asyncio_gather(
                    self._rpc(session, "getTokenLargestAccounts", [mint, {"commitment": "confirmed"}]),
                    self._rpc(session, "getTokenSupply", [mint, {"commitment": "confirmed"}]),
                )
            accounts = (largest or {}).get("value") or []
            supply_value = (supply or {}).get("value") or {}
            total = int(supply_value.get("amount") or 0)
            if total <= 0:
                return {"status": "UNKNOWN", "reason": "Token supply unavailable"}
            amounts = [int(item.get("amount") or 0) for item in accounts]
            top10 = sum(amounts[:10])
            top20 = sum(amounts[:20])
            return {
                "status": "PARTIAL",
                "accounts_returned": len(amounts),
                "top10_token_account_share_pct": round(top10 / total * 100, 2),
                "top20_token_account_share_pct": round(top20 / total * 100, 2),
                "warning": "Largest token accounts are not necessarily individual holders; LP and exchange vaults may distort concentration.",
                "limitations": ["Only the largest 20 token accounts are returned",
                                "No owner-wallet aggregation or LP-vault classification",
                                "This estimate must not be treated as a complete holder distribution"],
            }
        except Exception as error:
            return {"status": "UNKNOWN", "reason": f"{type(error).__name__}: {error}"}


async def asyncio_gather(*tasks):
    import asyncio
    return await asyncio.gather(*tasks)
