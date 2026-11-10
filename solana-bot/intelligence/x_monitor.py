"""Optional official X API v2 recent-search adapter.

Requires an X API bearer token supplied locally through X_BEARER_TOKEN.
This module never scrapes logged-in browser sessions and never triggers trades.
"""
import time
import aiohttp

SEARCH_URL = "https://api.x.com/2/tweets/search/recent"


def normalise_response(payload):
    users = {
        item.get("id"): item
        for item in (payload.get("includes") or {}).get("users", [])
        if item.get("id")
    }
    posts = []
    for item in payload.get("data") or []:
        author = users.get(item.get("author_id"), {})
        metrics = author.get("public_metrics") or {}
        post_metrics = item.get("public_metrics") or {}
        posts.append({
            "id": item.get("id"),
            "text": item.get("text") or "",
            "created_at": item.get("created_at"),
            "author_id": item.get("author_id"),
            "username": author.get("username") or item.get("author_id") or "unknown",
            "verified_badge": bool(author.get("verified", False)),
            "followers_count": int(metrics.get("followers_count") or 0),
            "like_count": int(post_metrics.get("like_count") or 0),
            "repost_count": int(post_metrics.get("retweet_count") or 0),
        })
    return posts


class XMonitor:
    def __init__(self, bearer_token="", query="solana (CA OR contract OR launched OR pump.fun) -is:retweet lang:en",
                 poll_interval_seconds=300):
        self.bearer_token = (bearer_token or "").strip()
        self.query = (query or "").strip()
        self.poll_interval = max(60, int(poll_interval_seconds))
        self.last_poll = 0.0
        self.since_id = None

    async def poll(self, force=False):
        if not self.bearer_token:
            return {"status": "DISABLED", "posts": [], "reason": "X_BEARER_TOKEN is not configured"}
        now = time.time()
        if not force and now - self.last_poll < self.poll_interval:
            return {"status": "WAIT", "posts": []}
        self.last_poll = now
        params = {
            "query": self.query,
            "max_results": 100,
            "tweet.fields": "created_at,public_metrics,lang,author_id",
            "expansions": "author_id",
            "user.fields": "username,verified,public_metrics",
        }
        if self.since_id:
            params["since_id"] = self.since_id
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(SEARCH_URL, params=params) as response:
                    response.raise_for_status()
                    payload = await response.json()
            meta = payload.get("meta") or {}
            newest = meta.get("newest_id")
            if newest:
                self.since_id = newest
            return {
                "status": "OK",
                "posts": normalise_response(payload),
                "result_count": meta.get("result_count", 0),
            }
        except Exception as error:
            return {"status": "ERROR", "posts": [], "reason": f"{type(error).__name__}: {error}"}
