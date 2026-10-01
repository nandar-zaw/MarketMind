"""
Technical Analysis Agent placeholder.

Future responsibility:
Analyze technical indicators such as RSI, SMA, MACD,
volume trend, and short-term price trend.
"""

from app.agents.base_agent import BaseAgent


class TechnicalAgent(BaseAgent):
    """
    Future responsibility:
    Analyze technical indicators such as RSI, SMA and MACD.
    """

    name = "technical_agent"

    async def analyze(self, ticker: str):
        # TODO: In Phase 2, compute RSI, SMA, MACD, and volume trend.
        raise NotImplementedError(
            "Technical analysis will be implemented in Phase 2."
        )
