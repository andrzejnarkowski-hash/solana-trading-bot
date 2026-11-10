import unittest
from risk.onchain import TOKEN_PROGRAM, TOKEN_2022_PROGRAM, parse_mint_account


def base_mint():
    raw = bytearray(82)
    raw[45] = 1  # initialized
    return raw


class MintParserTests(unittest.TestCase):
    def test_classic_mint_with_revoked_authorities(self):
        result = parse_mint_account(TOKEN_PROGRAM, bytes(base_mint()))
        self.assertEqual(result["status"], "PARSED")
        self.assertFalse(result["mint_authority_active"])
        self.assertFalse(result["freeze_authority_active"])
        self.assertEqual(result["risks"], [])

    def test_active_mint_authority_is_a_risk(self):
        raw = base_mint()
        raw[0:4] = (1).to_bytes(4, "little")
        raw[4:36] = bytes([7]) * 32
        result = parse_mint_account(TOKEN_PROGRAM, bytes(raw))
        self.assertIn("Mint authority is active", result["risks"])

    def test_uninitialized_mint_is_unknown(self):
        raw = base_mint()
        raw[45] = 0
        self.assertEqual(parse_mint_account(TOKEN_PROGRAM, bytes(raw))["status"], "UNKNOWN")

    def test_token_2022_permanent_delegate_is_risk(self):
        raw = bytearray(166)
        raw[45] = 1
        raw[165] = 1
        raw.extend((12).to_bytes(2, "little"))
        raw.extend((32).to_bytes(2, "little"))
        raw.extend(bytes([9]) * 32)
        result = parse_mint_account(TOKEN_2022_PROGRAM, bytes(raw))
        self.assertEqual(result["status"], "PARSED")
        self.assertIn("Permanent delegate is active", result["risks"])

    def test_malformed_extension_length_is_unknown(self):
        raw = bytearray(166)
        raw[45] = 1
        raw[165] = 1
        raw.extend((12).to_bytes(2, "little"))
        raw.extend((100).to_bytes(2, "little"))
        raw.extend(bytes([9]) * 32)
        self.assertEqual(parse_mint_account(TOKEN_2022_PROGRAM, bytes(raw))["status"], "UNKNOWN")

    def test_unknown_program_is_unknown(self):
        self.assertEqual(parse_mint_account("not-a-token-program", bytes(base_mint()))["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
