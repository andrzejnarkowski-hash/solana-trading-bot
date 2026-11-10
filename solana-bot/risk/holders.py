"""Partial concentration analysis using the largest SPL token accounts.

The RPC endpoint exposes only the largest 20 token accounts. We decode their
embedded token-owner addresses and aggregate duplicate accounts by owner wallet.
This is still not a full holder map and does not classify LP/program vaults.
"""
import base64
import aiohttp

RPC_URL = "https://api.mainnet-beta.solana.com"


def base58_encode(data):
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    zeros = len(data) - len(data.lstrip(bytes([0])))
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    return "1" * zeros + encoded


def concentration_from_amounts(amounts, total_supply):
    total = int(total_supply or 0)
    if total <= 0:
        return None
    values = sorted((max(0, int(value or 0)) for value in amounts), reverse=True)
    return {
        "top10_token_account_share_pct": round(sum(values[:10]) / total * 100, 2),
        "top20_token_account_share_pct": round(sum(values[:20]) / total * 100, 2),
    }


def aggregate_owner_amounts(account_payloads):
    """Return aggregate raw token amounts keyed by token-account owner wallet."""
    owners = {}
    parsed = 0
    for item in account_payloads or []:
        if not isinstance(item, dict):
            continue
        try:
            encoded = (item.get("data") or [None])[0]
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) < 72:
                continue
            owner = base58_encode(raw[32:64])
            amount = int.from_bytes(raw[64:72], "little")
            if owner:
                owners[owner] = owners.get(owner, 0) + amount
                parsed += 1
        except (TypeError, ValueError, IndexError):
            continue
    return owners, parsed


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
                largest_accounts = (largest or {}).get("value") or []
                addresses = [item.get("address") for item in largest_accounts if item.get("address")]
                account_result = await self._rpc(
                    session, "getMultipleAccounts",
                    [addresses, {"encoding": "base64", "commitment": "confirmed"}],
                ) if addresses else {"value": []}

            supply_value = (supply or {}).get("value") or {}
            total = int(supply_value.get("amount") or 0)
            if total <= 0:
                return {"status": "UNKNOWN", "reason": "Token supply unavailable"}
            payloads = (account_result or {}).get("value") or []
            owners, parsed = aggregate_owner_amounts(payloads)
            if not parsed:
                return {"status": "UNKNOWN", "reason": "Could not decode largest token accounts"}
            shares = concentration_from_amounts(owners.values(), total)
            return {
                "status": "PARTIAL",
                "token_accounts_returned": len(addresses),
                "token_accounts_decoded": parsed,
                "unique_owners_in_top_accounts": len(owners),
                "top10_wallet_share_pct": shares["top10_token_account_share_pct"],
                "top20_wallet_share_pct": shares["top20_token_account_share_pct"],
                "warning": "Wallets are aggregated only among the largest 20 token accounts; LP, exchange and program vaults are not classified.",
                "limitations": [
                    "Only the largest 20 token accounts are examined",
                    "Wallets with several top accounts are aggregated, but smaller accounts outside the top 20 are missed",
                    "LP, exchange, vesting, custody and program vaults are not classified",
                    "This is not a complete holder distribution or a rug-pull verdict",
                ],
            }
        except Exception as error:
            return {"status": "UNKNOWN", "reason": f"{type(error).__name__}: {error}"}


async def asyncio_gather(*tasks):
    import asyncio
    return await asyncio.gather(*tasks)
