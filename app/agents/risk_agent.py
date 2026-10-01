"""
Risk Manager Agent placeholder.

Future responsibility:
Assess volatility, recent price swings, event risk,
and produce a basic risk level for the ticker.
"""

from app.agents.base_agent import BaseAgent


class RiskAgent(BaseAgent):
    """
    Future responsibility:
    Evaluate risk factors and adjust recommendations for safety.
    """

    name = "risk_agent"

    async def analyze(self, ticker: str):
        # TODO: In Phase 5, compute volatility and event risk.
        raise NotImplementedError(
            "Risk analysis will be implemented in Phase 5."
        )
