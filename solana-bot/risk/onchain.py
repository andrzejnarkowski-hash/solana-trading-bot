import aiohttp
import base64

RPC_URL = "https://api.mainnet-beta.solana.com"

TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

EXTENSIONS = {
    1: "Transfer Fee Config",
    3: "Mint Close Authority",
    4: "Confidential Transfer",
    6: "Default Account State",
    9: "Non-Transferable",
    10: "Interest Bearing",
    12: "Permanent Delegate",
    14: "Transfer Hook",
    16: "Confidential Transfer Fee",
    18: "Metadata Pointer",
    19: "Token Metadata",
    20: "Group Pointer",
    21: "Token Group",
    22: "Group Member Pointer",
    23: "Token Group Member",
    24: "Confidential Mint-Burn",
    25: "Scaled UI Amount",
    26: "Pausable",
    28: "Permissioned Burn",
}


def has_authority(data):
    return len(data) >= 32 and any(data[:32])


class OnChainSecurity:

    async def check_mint(self, address):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [
                address,
                {"encoding": "base64", "commitment": "confirmed"}
            ]
        }

        try:
            timeout = aiohttp.ClientTimeout(total=20)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(RPC_URL, json=payload) as response:
                    response.raise_for_status()
                    result = await response.json()

            if "error" in result:
                return {
                    "status": "UNKNOWN",
                    "reason": str(result["error"])
                }

            account = result.get("result", {}).get("value")

            if account is None:
                return {
                    "status": "UNKNOWN",
                    "reason": "Mint account not found"
                }

            owner = account.get("owner")

            if owner not in {TOKEN_PROGRAM, TOKEN_2022_PROGRAM}:
                return {
                    "status": "UNKNOWN",
                    "reason": "Unrecognized token program"
                }

            encoded_data = account.get("data", [None])[0]

            if not encoded_data:
                return {
                    "status": "UNKNOWN",
                    "reason": "Missing account data"
                }

            raw = base64.b64decode(encoded_data)

            if len(raw) < 82:
                return {
                    "status": "UNKNOWN",
                    "reason": "Invalid mint account data"
                }

            # Standard SPL mint fields
            mint_authority = int.from_bytes(raw[0:4], "little") != 0
            freeze_authority = int.from_bytes(raw[46:50], "little") != 0

            risks = []
            warnings = []
            extensions = []

            if mint_authority:
                risks.append("Mint authority is active")

            if freeze_authority:
                risks.append("Freeze authority is active")

            # Classic SPL Token has no Token-2022 extensions.
            if owner == TOKEN_PROGRAM:
                return {
                    "status": "PARSED",
                    "token_program": "SPL Token",
                    "mint_authority_active": mint_authority,
                    "freeze_authority_active": freeze_authority,
                    "extensions": [],
                    "risks": risks,
                    "warnings": warnings,
                }

            # Token-2022 extension data starts after the base mint,
            # padding and account-type byte.
            if len(raw) == 82:
                return {
                    "status": "PARSED",
                    "token_program": "Token-2022",
                    "mint_authority_active": mint_authority,
                    "freeze_authority_active": freeze_authority,
                    "extensions": [],
                    "risks": risks,
                    "warnings": warnings,
                }

            if len(raw) < 166:
                return {
                    "status": "UNKNOWN",
                    "reason": "Unexpected Token-2022 account layout"
                }

            account_type = raw[165]

            if account_type != 1:
                return {
                    "status": "UNKNOWN",
                    "reason": f"Unexpected account type: {account_type}"
                }

            # Parse the extension TLV records.
            offset = 166

            while offset + 4 <= len(raw):
                extension_type = int.from_bytes(
                    raw[offset:offset + 2], "little"
                )
                extension_length = int.from_bytes(
                    raw[offset + 2:offset + 4], "little"
                )
                offset += 4

                if extension_type == 0 and extension_length == 0:
                    break

                end = offset + extension_length

                if end > len(raw):
                    return {
                        "status": "UNKNOWN",
                        "reason": "Malformed extension data"
                    }

                value = raw[offset:end]
                offset = end

                name = EXTENSIONS.get(
                    extension_type,
                    f"Unknown extension ({extension_type})"
                )

                extensions.append(name)

                if extension_type == 12:
                    if has_authority(value):
                        risks.append("Permanent delegate is active")
                    else:
                        warnings.append(
                            "Permanent Delegate extension present; "
                            "delegate appears unset"
                        )

                elif extension_type == 14:
                    if len(value) < 64:
                        risks.append("Malformed Transfer Hook extension")
                    elif any(value[32:64]):
                        risks.append(
                            "Custom Transfer Hook program configured"
                        )
                    else:
                        warnings.append(
                            "Transfer Hook extension present; "
                            "program appears unset"
                        )

                elif extension_type == 26:
                    if len(value) < 33:
                        risks.append("Malformed Pausable extension")
                    else:
                        paused = value[32] != 0
                        if paused:
                            risks.append("Token transfers are paused")
                        if has_authority(value):
                            risks.append("Pausable authority is active")

                elif extension_type == 6:
                    if len(value) >= 1 and value[0] == 2:
                        risks.append(
                            "Default token account state is FROZEN"
                        )

                elif extension_type == 9:
                    risks.append("Token is non-transferable")

                elif extension_type == 1:
                    warnings.append(
                        "Transfer fees configured; actual received "
                        "amount may be lower"
                    )

                elif extension_type == 3:
                    if has_authority(value):
                        risks.append("Mint close authority is active")

                elif extension_type == 4:
                    warnings.append(
                        "Confidential Transfer extension: requires review"
                    )

                elif extension_type == 16:
                    warnings.append(
                        "Confidential Transfer Fee extension: requires review"
                    )

                elif extension_type == 28:
                    risks.append(
                        "Permissioned Burn extension present"
                    )

                elif extension_type not in EXTENSIONS:
                    risks.append(
                        f"Unrecognized extension {extension_type}; "
                        "manual review required"
                    )

            return {
                "status": "PARSED",
                "token_program": "Token-2022",
                "mint_authority_active": mint_authority,
                "freeze_authority_active": freeze_authority,
                "extensions": extensions,
                "risks": risks,
                "warnings": warnings,
            }

        except Exception as error:
            return {
                "status": "UNKNOWN",
                "reason": str(error)
            }
