"""Tests for NewsDataService normalization (no network)."""

import pytest

import app.services.news_data as news_module
from app.services.news_data import NewsDataService
from app.utils.exceptions import MarketDataError


@pytest.fixture(autouse=True)
def _clear_cache():
    news_module._CACHE.clear()
    yield
    news_module._CACHE.clear()


CURRENT_SHAPE = [
    {
        "content": {
            "title": "Apple beats earnings estimates",
            "summary": "Profit rose sharply in the quarter.",
            "pubDate": "2026-10-04T12:00:00Z",
            "provider": {"displayName": "Reuters"},
        }
    },
    {"content": {"title": "", "provider": {"displayName": "Nowhere"}}},
]

LEGACY_SHAPE = [
    {
        "title": "Analysts raise Apple price target",
        "publisher": "Bloomberg",
        "providerPublishTime": 1759488000,
        "summary": "",
    }
]


def test_normalizes_current_yfinance_shape():
    service = NewsDataService(fetcher=lambda ticker: list(CURRENT_SHAPE))
    items = service.get_recent_news("AAPL")
    # Empty-title items are dropped.
    assert len(items) == 1
    assert items[0].title == "Apple beats earnings estimates"
    assert items[0].publisher == "Reuters"
    assert items[0].published == "2026-10-04"
    assert items[0].summary.startswith("Profit rose")


def test_normalizes_legacy_yfinance_shape():
    service = NewsDataService(fetcher=lambda ticker: list(LEGACY_SHAPE))
    items = service.get_recent_news("MSFT")
    assert len(items) == 1
    assert items[0].publisher == "Bloomberg"
    assert items[0].published  # derived from the epoch timestamp


def test_empty_ticker_is_rejected():
    service = NewsDataService(fetcher=lambda ticker: [])
    with pytest.raises(MarketDataError, match="empty"):
        service.get_recent_news("  ")


def test_provider_failure_raises_market_data_error():
    def boom(ticker):
        raise RuntimeError("provider down")

    service = NewsDataService(fetcher=boom)
    with pytest.raises(MarketDataError, match="provider down"):
        service.get_recent_news("TSLA")
