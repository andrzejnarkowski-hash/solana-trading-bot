import unittest
from intelligence.x_monitor import normalise_response, XMonitor


class XMonitorTests(unittest.TestCase):
    def test_normalise_response_joins_author_and_public_metrics(self):
        payload = {
            "data": [{
                "id": "123", "text": "New Solana CA", "author_id": "u1",
                "public_metrics": {"like_count": 12, "retweet_count": 3},
            }],
            "includes": {"users": [{
                "id": "u1", "username": "sample", "verified": True,
                "public_metrics": {"followers_count": 456},
            }]},
        }
        posts = normalise_response(payload)
        self.assertEqual(posts[0]["username"], "sample")
        self.assertEqual(posts[0]["followers_count"], 456)
        self.assertEqual(posts[0]["like_count"], 12)
        self.assertTrue(posts[0]["verified_badge"])

    def test_no_token_disables_x_monitor_cleanly(self):
        import asyncio
        result = asyncio.run(XMonitor().poll())
        self.assertEqual(result["status"], "DISABLED")
        self.assertEqual(result["posts"], [])


if __name__ == "__main__":
    unittest.main()
