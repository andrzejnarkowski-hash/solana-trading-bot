import unittest
from intelligence.ca_detector import extract_addresses, is_valid_solana_address
from intelligence.announcement import analyze_announcement
from intelligence.influencers import calculate_signal_priority


KNOWN_CA = "DigVnUDwgbSSWNMNsgzGNw8EQhqwjniPU2EsfD4Wpump"


class SignalTests(unittest.TestCase):
    def test_valid_ca_is_extracted(self):
        self.assertEqual(extract_addresses("Official CA: " + KNOWN_CA), [KNOWN_CA])

    def test_invalid_string_is_not_a_ca(self):
        self.assertFalse(is_valid_solana_address("not-a-solana-address"))
        self.assertEqual(extract_addresses("not-a-solana-address"), [])

    def test_negative_warning_overrides_launch_phrase(self):
        result = analyze_announcement("I just launched it but do not buy, fake CA", [KNOWN_CA])
        self.assertEqual(result["signal"], "NEGATIVE")
        self.assertEqual(result["confidence"], 0)

    def test_unlisted_author_is_not_trusted(self):
        result = calculate_signal_priority("random_account", {
            "signal": "POSSIBLE_LAUNCH", "confidence": 100
        })
        self.assertEqual(result["priority"], "LOW")
        self.assertEqual(result["score"], 0)


if __name__ == "__main__":
    unittest.main()
