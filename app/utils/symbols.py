"""
Market symbol constants for MarketMind.

MarketMind focuses on the S&P 500 for this course project.
We use SPY (the S&P 500 ETF) as the Yahoo Finance / yfinance symbol
because it is liquid, has volume data for technical analysis, and
passes simple ticker validation. The cash index ^GSPC is accepted as
an alias and resolved to SPY.
"""

# Primary market symbol used across the app (UI default, docs, demos).
SP500_SYMBOL = "SPY"

# Common names for the S&P 500 → resolved to SP500_SYMBOL before fetch.
SP500_ALIASES = {
    "SPY": SP500_SYMBOL,
    "SP": SP500_SYMBOL,  # common shorthand in the UI
    "SPX": SP500_SYMBOL,
    "GSPC": SP500_SYMBOL,
    "^GSPC": SP500_SYMBOL,
    "SP500": SP500_SYMBOL,
    "S&P500": SP500_SYMBOL,
    "S&P 500": SP500_SYMBOL,
}


def resolve_market_symbol(ticker: str) -> str:
    """
    Normalize a ticker and map S&P 500 aliases to SPY.

    Examples:
        resolve_market_symbol(" spy ") -> "SPY"
        resolve_market_symbol("^GSPC") -> "SPY"
        resolve_market_symbol("spx") -> "SPY"
        resolve_market_symbol("AAPL") -> "AAPL"  # still allowed by API
    """
    cleaned = (ticker or "").strip().upper()
    collapsed = cleaned.replace(" ", "")
    if cleaned in SP500_ALIASES:
        return SP500_ALIASES[cleaned]
    if collapsed in SP500_ALIASES:
        return SP500_ALIASES[collapsed]
    return cleaned
