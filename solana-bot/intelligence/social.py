"""Collect token social metadata without treating self-reported links as proof."""
import aiohttp
from urllib.parse import urlparse

DEX_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"
SOCIAL_DOMAINS = {
    "x.com", "twitter.com", "t.me", "telegram.me", "discord.gg",
    "discord.com", "instagram.com", "tiktok.com", "youtube.com", "youtu.be",
}


def _normalise_url(value, platform=None):
    value = (value or "").strip()
    if not value:
        return None
    if value.startswith("@"):
        if platform in ("x", "twitter"):
            return "https://x.com/" + value[1:]
        if platform == "telegram":
            return "https://t.me/" + value[1:]
        return None
    if "://" not in value:
        if platform in ("x", "twitter") and "/" not in value and "." not in value:
            return "https://x.com/" + value.lstrip("@")
        if platform == "telegram" and "/" not in value and "." not in value:
            return "https://t.me/" + value.lstrip("@")
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return value


class SocialIntelligence:
    async def analyze(self, token):
        address = token.get("address")
        if not address:
            return {"status": "UNKNOWN", "score": None,
                    "warnings": ["Missing token address"]}
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(DEX_URL.format(address)) as response:
                    response.raise_for_status()
                    data = await response.json()
            pairs = data.get("pairs") or []
            if not pairs:
                return {"status": "UNKNOWN", "score": None,
                        "warnings": ["No pair metadata"]}
            pair = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
            info = pair.get("info") or {}
            profiles, posts, telegram, other, websites, warnings = [], [], [], [], [], []
            for item in info.get("socials") or []:
                platform = (item.get("type") or "").lower()
                raw = item.get("url") or item.get("handle") or ""
                url = _normalise_url(raw, platform)
                if not url:
                    warnings.append("Unusable social metadata entry")
                    continue
                host = (urlparse(url).hostname or "").lower()
                path = urlparse(url).path.strip("/")
                if host in ("x.com", "www.x.com", "twitter.com", "www.twitter.com"):
                    (posts if "/status/" in path else profiles).append(url)
                elif host in ("t.me", "www.t.me", "telegram.me"):
                    telegram.append(url)
                else:
                    other.append(url)
            for item in info.get("websites") or []:
                url = _normalise_url(item.get("url"))
                if url:
                    websites.append(url)
            if not profiles and not posts and not telegram and not other and not websites:
                warnings.append("No usable social links found")
            if websites:
                warnings.append("Website links are self-reported and not verified against token ownership")
            if profiles or posts or telegram or other:
                warnings.append("Social links do not prove account ownership, activity, or community quality")
            return {
                "status": "CHECKED",
                "score": None,
                "x_profiles": sorted(set(profiles)),
                "x_posts": sorted(set(posts)),
                "telegram": sorted(set(telegram)),
                "other_socials": sorted(set(other)),
                "websites": sorted(set(websites)),
                "warnings": warnings,
                "limitations": [
                    "DexScreener metadata is self-reported",
                    "X account identity and engagement are not verified",
                    "Website/token ownership is not verified",
                    "Social metadata is not used as a buy signal",
                ],
            }
        except Exception as error:
            return {"status": "UNKNOWN", "score": None,
                    "warnings": [f"{type(error).__name__}: {error}"]}
