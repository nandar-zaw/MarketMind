"""Tests for S&P 500 symbol focus and alias resolution."""

from app.utils.helpers import normalize_ticker
from app.utils.symbols import SP500_SYMBOL, resolve_market_symbol


def test_sp500_primary_symbol_is_spy():
    assert SP500_SYMBOL == "SPY"


def test_normalize_resolves_sp500_aliases():
    assert normalize_ticker("^GSPC") == "SPY"
    assert normalize_ticker("spx") == "SPY"
    assert normalize_ticker(" SPY ") == "SPY"


def test_resolve_keeps_non_index_tickers():
    assert resolve_market_symbol("AAPL") == "AAPL"
