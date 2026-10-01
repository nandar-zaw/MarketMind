"""
Market data service placeholder.

Future responsibility:
Fetch historical stock prices and basic company information
(for example via yfinance or another data source).

Phase 1 does not call any market APIs.
"""


class MarketDataService:
    """
    Placeholder for stock price and company data access.

    TODO: Implement real data download in Phase 2.
    """

    def get_price_history(self, ticker: str, days: int = 90):
        """
        Return historical OHLCV price data for a ticker.

        Not implemented in Phase 1.
        """
        raise NotImplementedError(
            "Market price history will be implemented in Phase 2."
        )

    def get_company_info(self, ticker: str):
        """
        Return basic company information for a ticker.

        Not implemented in Phase 1.
        """
        raise NotImplementedError(
            "Company info lookup will be implemented in Phase 2."
        )
