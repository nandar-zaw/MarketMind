"""
Small helper functions used across MarketMind.

Keep helpers simple and easy to explain in class.
"""


def normalize_ticker(ticker: str) -> str:
    """
    Normalize a ticker symbol to uppercase with no surrounding spaces.

    Example:
        normalize_ticker(" aapl ") -> "AAPL"
    """
    return ticker.strip().upper()
