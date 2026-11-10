import aiohttp
from urllib.parse import urlparse

DEX_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"

SOCIAL_DOMAINS = {
    "x.com", "twitter.com",
    "t.me", "telegram.me",
    "discord.gg", "discord.com",
    "instagram.com", "tiktok.com",
    "youtube.com", "youtu.be"
}


class SocialIntelligence:

    async def analyze(self, token):
        address = token.get("address")

        if not address:
            return {
                "status": "UNKNOWN",
                "score": None,
                "warnings": ["Missing token address"]
            }

        try:
            timeout = aiohttp.ClientTimeout(total=15)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(DEX_URL.format(address)) as response:
                    response.raise_for_status()
                    data = await response.json()

            pairs = data.get("pairs") or []

            if not pairs:
                return {
                    "status": "UNKNOWN",
                    "score": None,
                    "warnings": ["No pair metadata"]
                }

            pair = max(
                pairs,
                key=lambda p: (p.get("liquidity") or {}).get("usd") or 0
            )

            info = pair.get("info") or {}
            socials = info.get("socials") or []
            websites = info.get("websites") or []

            x_profiles = []
            x_posts = []
            telegram = []
            other_socials = []
            project_links = []
            warnings = []

            def get_host(url):
                try:
                    if not url.startswith(("http://", "https://")):
                        url = "https://" + url
                    return (urlparse(url).hostname or "").lower()
                except Exception:
                    return ""

            def is_domain(host, domain):
                return host == domain or host.endswith("." + domain)

            all_links = []

            for item in socials:
                platform = (item.get("type") or "").lower()
                handle = (item.get("handle") or "").strip()

                if not handle:
                    continue

                if platform in ("twitter", "x"):
                    all_links.append(handle)
                elif platform == "telegram":
                    telegram.append(handle)
                else:
                    other_socials.append(platform)

            for item in websites:
                url = (item.get("url") or "").strip()

                if url:
                    all_links.append(url)

            for link in all_links:
                host = get_host(link)

                if not host:
                    warnings.append("Invalid social link")
                    continue

                if is_domain(host, "x.com") or is_domain(host, "twitter.com"):
                    path = urlparse(
                        link if link.startswith(("http://", "https://"))
                        else "https://" + link
                    ).path.strip("/")

                    if path and "/status/" in path:
                        x_posts.append(link)
                    elif path and len(path.split("/")) == 1:
                        x_profiles.append(link)
                    else:
                        warnings.append("X link is not a clear profile")

                elif is_domain(host, "t.me") or is_domain(host, "telegram.me"):
                    telegram.append(link)

                elif any(is_domain(host, d) for d in SOCIAL_DOMAINS):
                    other_socials.append(host)

                else:
                    project_links.append(link)

            score = 0

            if x_profiles:
                score += 30

            if project_links:
                score += 20

            if telegram:
                score += 15

            if other_socials:
                score += min(15, len(set(other_socials)) * 5)

            has_data = bool(
                x_profiles or project_links or telegram or other_socials
            )

            if x_posts:
                warnings.append(
                    "X posts found, but no verified project profile"
                )

            if project_links:
                warnings.append(
                    "Website relevance to this token has not been verified"
                )

            if not has_data:
                warnings.append("No usable social links found")

            return {
                "status": "CHECKED" if has_data else "INSUFFICIENT_DATA",
                "score": score if has_data else None,
                "x_profiles": x_profiles,
                "x_posts": x_posts,
                "project_links": project_links,
                "telegram": telegram,
                "other_socials": other_socials,
                "warnings": warnings,
                "limitations": [
                    "Links are self-reported metadata",
                    "X account ownership and activity are not verified",
                    "Website relevance is not verified",
                    "This score does not prove legitimacy"
                ]
            }

        except Exception as error:
            return {
                "status": "UNKNOWN",
                "score": None,
                "warnings": [str(error)]
            }
