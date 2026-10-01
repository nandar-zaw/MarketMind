"""
Fundamental Analysis Agent placeholder.

Future responsibility:
Analyze company fundamentals such as revenue growth, earnings,
P/E ratio, debt levels, and overall financial health.
"""

from app.agents.base_agent import BaseAgent


class FundamentalAgent(BaseAgent):
    """
    Future responsibility:
    Analyze company financial health and valuation metrics.
    """

    name = "fundamental_agent"

    async def analyze(self, ticker: str):
        # TODO: In Phase 4, analyze revenue, earnings, P/E, and debt.
        raise NotImplementedError(
            "Fundamental analysis will be implemented in Phase 4."
        )
