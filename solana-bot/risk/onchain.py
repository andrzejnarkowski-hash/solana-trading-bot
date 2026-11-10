"""Conservative SPL / Token-2022 mint inspection. A parsed mint is not a safety verdict."""
import aiohttp
import base64

RPC_URL = "https://api.mainnet-beta.solana.com"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
EXTENSIONS = {
    1: "Transfer Fee Config", 3: "Mint Close Authority", 4: "Confidential Transfer",
    6: "Default Account State", 9: "Non-Transferable", 10: "Interest Bearing",
    12: "Permanent Delegate", 14: "Transfer Hook", 16: "Confidential Transfer Fee",
    18: "Metadata Pointer", 19: "Token Metadata", 20: "Group Pointer",
    21: "Token Group", 22: "Group Member Pointer", 23: "Token Group Member",
    24: "Confidential Mint-Burn", 25: "Scaled UI Amount", 26: "Pausable",
    28: "Permissioned Burn",
}


def _coption_authority(raw, offset):
    tag = int.from_bytes(raw[offset:offset + 4], "little")
    if tag not in (0, 1):
        raise ValueError("Invalid COption authority tag")
    key = raw[offset + 4:offset + 36]
    if len(key) != 32:
        raise ValueError("Truncated authority public key")
    if tag == 1 and not any(key):
        raise ValueError("Authority tag is set but public key is zero")
    return tag == 1


def _parse_extensions(raw):
    offset, seen = 166, set()
    extensions, risks, warnings = [], [], []
    while offset < len(raw):
        if not any(raw[offset:]):
            break
        if len(raw) - offset < 4:
            raise ValueError("Truncated Token-2022 extension header")
        ext_type = int.from_bytes(raw[offset:offset + 2], "little")
        ext_len = int.from_bytes(raw[offset + 2:offset + 4], "little")
        offset += 4
        if ext_type == 0 or ext_type in seen:
            raise ValueError("Invalid or duplicate extension type")
        seen.add(ext_type)
        end = offset + ext_len
        if end > len(raw):
            raise ValueError("Malformed extension data length")
        value = raw[offset:end]
        offset = end
        extensions.append(EXTENSIONS.get(ext_type, f"Unknown extension ({ext_type})"))
        if ext_type in (3, 12):
            if len(value) != 32:
                raise ValueError("Malformed authority extension")
            if any(value):
                risks.append("Mint close authority is active" if ext_type == 3 else "Permanent delegate is active")
        elif ext_type == 14:
            if len(value) != 64:
                raise ValueError("Malformed Transfer Hook extension")
            if any(value[32:]):
                risks.append("Custom Transfer Hook program configured")
            else:
                warnings.append("Transfer Hook extension present; program appears unset")
        elif ext_type == 26:
            if len(value) != 33 or value[32] not in (0, 1):
                raise ValueError("Malformed Pausable extension")
            if value[32] == 1:
                risks.append("Token transfers are paused")
            if any(value[:32]):
                risks.append("Pausable authority is active")
        elif ext_type == 6:
            if len(value) != 1 or value[0] not in (0, 1, 2):
                raise ValueError("Malformed Default Account State extension")
            if value[0] == 2:
                risks.append("Default token account state is FROZEN")
        elif ext_type == 9:
            if value:
                raise ValueError("Malformed Non-Transferable extension")
            risks.append("Token is non-transferable")
        elif ext_type == 1:
            if len(value) != 108:
                raise ValueError("Malformed Transfer Fee Config extension")
            warnings.append("Transfer fees configured; inspect fee parameters before trading")
        elif ext_type in (4, 16):
            warnings.append(f"{EXTENSIONS[ext_type]} extension requires manual review")
        elif ext_type == 28:
            risks.append("Permissioned Burn extension present")
        elif ext_type in (10, 18, 19, 20, 21, 22, 23, 24, 25):
            warnings.append(f"{EXTENSIONS[ext_type]} extension requires manual review")
        else:
            risks.append(f"Unrecognized extension {ext_type}; manual review required")
    return extensions, risks, warnings


def parse_mint_account(owner, raw):
    if owner not in (TOKEN_PROGRAM, TOKEN_2022_PROGRAM):
        return {"status": "UNKNOWN", "reason": "Unrecognized token program"}
    if len(raw) < 82:
        return {"status": "UNKNOWN", "reason": "Invalid mint account data"}
    try:
        mint_authority = _coption_authority(raw, 0)
        if raw[45] != 1:
            return {"status": "UNKNOWN", "reason": "Mint is not initialized"}
        freeze_authority = _coption_authority(raw, 46)
    except ValueError as error:
        return {"status": "UNKNOWN", "reason": str(error)}
    risks, warnings = [], []
    if mint_authority:
        risks.append("Mint authority is active")
    if freeze_authority:
        risks.append("Freeze authority is active")
    if owner == TOKEN_PROGRAM:
        return {"status": "PARSED", "token_program": "SPL Token",
                "mint_authority_active": mint_authority, "freeze_authority_active": freeze_authority,
                "extensions": [], "risks": risks, "warnings": warnings}
    if len(raw) == 82:
        return {"status": "PARSED", "token_program": "Token-2022",
                "mint_authority_active": mint_authority, "freeze_authority_active": freeze_authority,
                "extensions": [], "risks": risks, "warnings": warnings}
    if len(raw) < 166 or raw[82:165] != bytes(83) or raw[165] != 1:
        return {"status": "UNKNOWN", "reason": "Unexpected Token-2022 mint layout"}
    try:
        extensions, ext_risks, ext_warnings = _parse_extensions(raw)
    except ValueError as error:
        return {"status": "UNKNOWN", "reason": str(error)}
    return {"status": "PARSED", "token_program": "Token-2022",
            "mint_authority_active": mint_authority, "freeze_authority_active": freeze_authority,
            "extensions": extensions, "risks": risks + ext_risks,
            "warnings": warnings + ext_warnings}


class OnChainSecurity:
    async def check_mint(self, address):
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
                   "params": [address, {"encoding": "base64", "commitment": "confirmed"}]}
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(RPC_URL, json=payload) as response:
                    response.raise_for_status()
                    result = await response.json()
            if "error" in result:
                return {"status": "UNKNOWN", "reason": str(result["error"])}
            account = result.get("result", {}).get("value")
            if account is None:
                return {"status": "UNKNOWN", "reason": "Mint account not found"}
            encoded = (account.get("data") or [None])[0]
            if not encoded:
                return {"status": "UNKNOWN", "reason": "Missing account data"}
            return parse_mint_account(account.get("owner"), base64.b64decode(encoded, validate=True))
        except Exception as error:
            return {"status": "UNKNOWN", "reason": f"{type(error).__name__}: {error}"}
