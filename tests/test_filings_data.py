"""Tests for FilingsDataService and the DataAgent filings fill.

The vector store search and the market/news services are faked, so
no network or API key is needed.
"""

import asyncio
from datetime import date

import pytest

from app.agents.data_agent import DataAgent
from app.models.schemas import CompanyInfo, FilingExcerpt, MarketPrice
from app.services import filings_data
from app.services.filings_data import FilingsDataService
from app.utils.exceptions import MarketDataError


@pytest.fixture(autouse=True)
def _clear_filings_cache():
    # FilingsDataService caches per ticker at module level; without
    # this, a real retrieval in another test (e.g. a live coordinator
    # run) would leak into these fake-searcher tests.
    filings_data._CACHE.clear()
    yield
    filings_data._CACHE.clear()


def _raw_item(text="Revenue grew 12% to $99.1B.", filename="AAPL_10-K.txt", score=0.91):
    return {
        "content": [{"type": "text", "text": text}],
        "filename": filename,
        "file_id": "file-123",
        "score": score,
    }


def test_unconfigured_store_returns_empty(monkeypatch):
    monkeypatch.delenv("FUNDAMENTALS_VECTOR_STORE_ID", raising=False)
    service = FilingsDataService(searcher=lambda *a: [_raw_item()])
    assert service.get_filing_evidence("AAPL") == []


def test_search_results_are_normalized(monkeypatch):
    monkeypatch.setenv("FUNDAMENTALS_VECTOR_STORE_ID", "vs_test")
    seen = {}

    def searcher(store_id, query, limit):
        seen.update(store_id=store_id, query=query, limit=limit)
        return [_raw_item(), {"content": [], "filename": "empty.txt"}]

    service = FilingsDataService(searcher=searcher)
    excerpts = service.get_filing_evidence("aapl", limit=5)
    assert seen["store_id"] == "vs_test"
    assert "AAPL" in seen["query"]
    assert len(excerpts) == 1  # empty-content item is dropped
    assert excerpts[0].source == "AAPL_10-K.txt"
    assert excerpts[0].score == 0.91
    assert "Revenue grew" in excerpts[0].text


def test_provider_failure_raises_market_data_error(monkeypatch):
    monkeypatch.setenv("FUNDAMENTALS_VECTOR_STORE_ID", "vs_test")

    def boom(store_id, query, limit):
        raise RuntimeError("api down")

    service = FilingsDataService(searcher=boom)
    with pytest.raises(MarketDataError):
        service.get_filing_evidence("ZZZZ")


class _FakeMarket:
    def get_ohlcv(self, symbol, **kwargs):
        return [
            MarketPrice(
                date=date(2026, 1, 5),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1_000_000,
            )
        ]

    def get_company_info(self, symbol):
        return CompanyInfo(ticker=symbol, company_name="Apple Inc.")


class _FakeNews:
    def get_recent_news(self, symbol):
        return []


class _FakeFilings:
    def __init__(self, excerpts=None, raises=False):
        self._excerpts = excerpts or []
        self._raises = raises

    def get_filing_evidence(self, symbol):
        if self._raises:
            raise MarketDataError("store down")
        return self._excerpts


def _agent(filings_service):
    return DataAgent(
        market_data_service=_FakeMarket(),
        news_data_service=_FakeNews(),
        filings_data_service=filings_service,
    )


def test_data_agent_fills_filings():
    excerpts = [FilingExcerpt(text="Revenue grew 12%.", source="AAPL_10-K.txt")]
    result = asyncio.run(_agent(_FakeFilings(excerpts)).analyze("AAPL"))
    assert len(result.filings) == 1
    assert result.filings[0].source == "AAPL_10-K.txt"


def test_data_agent_filings_outage_degrades_to_empty():
    result = asyncio.run(_agent(_FakeFilings(raises=True)).analyze("AAPL"))
    assert result.filings == []
    assert result.ticker == "AAPL"  # the rest of the pull still works
