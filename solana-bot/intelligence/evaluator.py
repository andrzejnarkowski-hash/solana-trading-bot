from intelligence.scoring import score_token
from intelligence.social import SocialIntelligence
from risk.onchain import OnChainSecurity


class CombinedEvaluator:

    def __init__(self):
        self.social = SocialIntelligence()
        self.security = OnChainSecurity()

    async def evaluate(self, token):
        market = score_token(token)

        security = await self.security.check_mint(token["address"])
        social = await self.social.analyze(token)

        if market["decision"] in ("REJECT", "SKIP"):
            decision = "REJECT"
        elif security["status"] != "PARSED":
            decision = "REVIEW"
        elif security.get("risks"):
            decision = "REJECT"
        elif market["decision"] == "WATCH":
            decision = "WATCH"
        else:
            decision = "MONITOR"

        return {
            "symbol": token["symbol"],
            "market_score": market["score"],
            "market_decision": market["decision"],
            "security": security,
            "social": social,
            "final_decision": decision
        }
