"""
Base class for all MarketMind agents.

Keep this simple so it is easy to explain in class.
"""


class BaseAgent:
    """
    Shared interface for specialized agents.

    Each agent has a name and an async analyze() method.
    """

    name: str = "base_agent"

    async def analyze(self, ticker: str):
        """
        Analyze a ticker and return an AgentResult later.

        Subclasses must implement this method.
        """
        raise NotImplementedError(
            f"{self.name} has not implemented analyze() yet."
        )
