"""
Data Collector Agent placeholder.

Future responsibility:
Download stock price data, collect basic company information,
and provide data to the other agents.
"""

from app.agents.base_agent import BaseAgent


class DataAgent(BaseAgent):
    """
    Future responsibility:
    Download stock price data, collect basic company information,
    and provide data to the other agents.
    """

    name = "data_agent"

    async def analyze(self, ticker: str):
        # TODO: In a later phase, fetch price history and company metadata.
        raise NotImplementedError(
            "Data collection will be implemented in Phase 2."
        )
