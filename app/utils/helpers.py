"""
Small helper functions used across MarketMind.

Keep helpers simple and easy to explain in class.
"""

from app.utils.symbols import resolve_market_symbol


def normalize_ticker(ticker: str) -> str:
    """
    Normalize a ticker symbol to uppercase with no surrounding spaces.

    S&P 500 aliases such as ^GSPC / SPX resolve to SPY.

    Example:
        normalize_ticker(" aapl ") -> "AAPL"
        normalize_ticker("^GSPC") -> "SPY"
    """
    return resolve_market_symbol(ticker)
