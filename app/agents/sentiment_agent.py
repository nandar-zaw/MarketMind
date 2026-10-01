"""
Sentiment Agent placeholder.

Future responsibility:
Collect recent company news and analyze positive / neutral / negative
sentiment, then summarize recent market sentiment.
"""

from app.agents.base_agent import BaseAgent


class SentimentAgent(BaseAgent):
    """
    Future responsibility:
    Collect recent company news and analyze sentiment.
    """

    name = "sentiment_agent"

    async def analyze(self, ticker: str):
        # TODO: In Phase 3, fetch news and score sentiment.
        raise NotImplementedError(
            "Sentiment analysis will be implemented in Phase 3."
        )
