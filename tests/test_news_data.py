"""Tests for NewsDataService normalization (no network)."""

import sys
import types

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


def test_empty_result_is_not_cached():
    # A transient empty response must not pin the ticker for the TTL:
    # the next call has to reach the provider again.
    responses = [[], list(LEGACY_SHAPE)]
    calls = {"n": 0}

    def flaky(ticker):
        calls["n"] += 1
        return responses.pop(0)

    service = NewsDataService(fetcher=flaky)
    assert service.get_recent_news("NVDA") == []
    items = service.get_recent_news("NVDA")
    assert len(items) == 1
    assert calls["n"] == 2


def test_search_empty_falls_back_to_ticker_news(monkeypatch):
    # When yfinance Search returns nothing, the raw fetch falls back
    # to the ticker feed (fake yfinance module: no network involved).
    class FakeSearch:
        def __init__(self, query, news_count=8):
            self.news = []

    class FakeTicker:
        def __init__(self, ticker):
            pass

        @property
        def news(self):
            return list(LEGACY_SHAPE)

    fake_yf = types.SimpleNamespace(Search=FakeSearch, Ticker=FakeTicker)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    service = NewsDataService()
    items = service.get_recent_news("ZZZZ")
    assert len(items) == 1
    assert items[0].publisher == "Bloomberg"
