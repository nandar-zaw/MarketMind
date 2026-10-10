"""
Small helper functions used across MarketMind.

Keep helpers simple and easy to explain in class.
"""

from app.utils.symbols import resolve_market_symbol


def normalize_ticker(ticker: str) -> str:
    """
    Normalize a ticker symbol and resolve S&P 500 aliases to SPY.

    Examples:
        normalize_ticker(" spy ") -> "SPY"
        normalize_ticker("^GSPC") -> "SPY"
        normalize_ticker(" aapl ") -> "AAPL"
    """
    return resolve_market_symbol(ticker)
