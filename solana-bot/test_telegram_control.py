import unittest

from telegram_control import TelegramControl


class FakeBroker:
    def log(self, *args, **kwargs):
        pass


class FakeEvent:
    def __init__(self):
        self.enabled = True

    def is_set(self):
        return self.enabled

    def set(self):
        self.enabled = True

    def clear(self):
        self.enabled = False


class TelegramControlTests(unittest.TestCase):
    def test_token_is_optional(self):
        self.assertFalse(TelegramControl("", "", FakeBroker()).enabled)

    def test_allowlist_parses_numeric_ids_and_ignores_invalid_values(self):
        control = TelegramControl("token-not-used-in-test", "123, abc, 456, , -7", FakeBroker())
        self.assertEqual(control.allowed_user_ids, {123, 456})

    def test_pause_and_resume_state(self):
        event = FakeEvent()
        control = TelegramControl("token", "123", FakeBroker(), event)
        self.assertTrue(control._entries_enabled())
        event.clear()
        self.assertFalse(control._entries_enabled())
        event.set()
        self.assertTrue(control._entries_enabled())


if __name__ == "__main__":
    unittest.main()
