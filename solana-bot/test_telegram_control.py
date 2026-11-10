import unittest

from telegram_control import TelegramControl


class FakeBroker:
    def log(self, *args, **kwargs):
        pass


class TelegramControlTests(unittest.TestCase):
    def test_token_is_optional(self):
        control = TelegramControl("", "", FakeBroker())
        self.assertFalse(control.enabled)

    def test_allowlist_parses_numeric_ids_and_ignores_invalid_values(self):
        control = TelegramControl("token-not-used-in-test", "123, abc, 456, , -7", FakeBroker())
        self.assertEqual(control.allowed_user_ids, {123, 456})
        self.assertTrue(control.enabled)

    def test_empty_allowlist_is_not_remote_access(self):
        control = TelegramControl("token-not-used-in-test", "", FakeBroker())
        self.assertEqual(control.allowed_user_ids, set())


if __name__ == "__main__":
    unittest.main()
