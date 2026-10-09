"""
Simple project-specific exceptions for MarketMind.

Keep the hierarchy small so it is easy to explain in class.
"""


class MarketDataError(Exception):
    """
    Raised when market data cannot be retrieved or validated.

    Examples: empty ticker, ticker not found, no price history,
    provider/network failure, or a malformed date.
    """
