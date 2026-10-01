"""
News data service placeholder.

Future responsibility:
Fetch recent company news headlines and article text
for sentiment analysis.

Phase 1 does not call any news APIs.
"""


class NewsDataService:
    """
    Placeholder for news article retrieval.

    TODO: Implement real news fetching in Phase 3.
    """

    def get_recent_news(self, ticker: str, limit: int = 10):
        """
        Return recent news items related to a ticker.

        Not implemented in Phase 1.
        """
        raise NotImplementedError(
            "News fetching will be implemented in Phase 3."
        )
