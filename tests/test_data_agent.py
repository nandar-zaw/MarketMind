"""
Unit tests for DataAgent and MarketDataService.

These tests mock yfinance so the normal suite does not need network access.
"""

import asyncio
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.agents.data_agent import DataAgent
from app.models.schemas import CompanyInfo, DataAgentResult, MarketPrice
from app.services.market_data import MarketDataService
from app.utils.exceptions import MarketDataError


def _sample_history_frame() -> pd.DataFrame:
    """Build a small OHLCV DataFrame that looks like yfinance output."""
    index = pd.to_datetime(
        ["2025-01-10", "2025-01-13", "2025-01-14", "2025-01-15", "2025-01-16"]
    )
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "Close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "Adj Close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "Volume": [1_000_000, 1_100_000, 1_200_000, 1_300_000, 1_400_000],
        },
        index=index,
    )


def _sample_company_info() -> dict:
    return {
        "longName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "exchange": "NMS",
        "currency": "USD",
        "marketCap": 3_000_000_000_000,
        "quoteType": "EQUITY",
        "symbol": "AAPL",
    }


class TestMarketDataService:
    def test_lowercase_ticker_becomes_uppercase(self):
        service = MarketDataService()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_history_frame()

        with patch("app.services.market_data.yf.Ticker", return_value=mock_ticker):
            prices = service.get_ohlcv(
                "aapl", start="2025-01-10", end="2025-01-16"
            )

        assert all(isinstance(p, MarketPrice) for p in prices)
        mock_ticker.history.assert_called()
        # The service normalizes before calling yfinance.
        with patch("app.services.market_data.yf.Ticker") as ticker_cls:
            ticker_cls.return_value.history.return_value = _sample_history_frame()
            service.get_ohlcv("aapl", start="2025-01-10", end="2025-01-16")
            ticker_cls.assert_called_with("AAPL")

    def test_empty_ticker_is_rejected(self):
        service = MarketDataService()
        with pytest.raises(MarketDataError, match="empty"):
            service.get_ohlcv("   ")

    def test_historical_data_is_mapped_correctly(self):
        service = MarketDataService()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_history_frame()

        with patch("app.services.market_data.yf.Ticker", return_value=mock_ticker):
            prices = service.get_ohlcv(
                "AAPL", start="2025-01-10", end="2025-01-16"
            )

        assert len(prices) == 5
        first = prices[0]
        assert first.date == date(2025, 1, 10)
        assert first.open == 100.0
        assert first.high == 105.0
        assert first.low == 99.0
        assert first.close == 104.0
        assert first.volume == 1_000_000
        assert first.adj_close == 104.0
        # Chronological order: oldest first.
        assert prices[0].date < prices[-1].date

    def test_company_metadata_is_mapped_correctly(self):
        service = MarketDataService()
        mock_ticker = MagicMock()
        mock_ticker.info = _sample_company_info()

        with patch("app.services.market_data.yf.Ticker", return_value=mock_ticker):
            info = service.get_company_info("aapl")

        assert isinstance(info, CompanyInfo)
        assert info.ticker == "AAPL"
        assert info.company_name == "Apple Inc."
        assert info.sector == "Technology"
        assert info.industry == "Consumer Electronics"
        assert info.exchange == "NMS"
        assert info.currency == "USD"
        assert info.market_cap == 3_000_000_000_000

    def test_empty_provider_response_is_handled(self):
        service = MarketDataService()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("app.services.market_data.yf.Ticker", return_value=mock_ticker):
            with pytest.raises(MarketDataError, match="No historical market data"):
                service.get_ohlcv("ZZZZ")

    def test_as_of_date_prevents_future_observations(self):
        service = MarketDataService()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_history_frame()

        with patch("app.services.market_data.yf.Ticker", return_value=mock_ticker):
            prices = service.get_ohlcv(
                "AAPL",
                start="2025-01-10",
                end="2025-01-16",
                as_of_date="2025-01-15",
            )

        assert prices
        assert all(p.date <= date(2025, 1, 15) for p in prices)
        assert prices[-1].date == date(2025, 1, 15)

    def test_malformed_date_raises_market_data_error(self):
        service = MarketDataService()
        with pytest.raises(MarketDataError, match="Invalid start"):
            service.get_ohlcv("AAPL", start="not-a-date")


class TestDataAgent:
    def test_data_agent_returns_expected_pydantic_structure(self):
        prices = [
            MarketPrice(
                date=date(2025, 1, 10),
                open=100.0,
                high=105.0,
                low=99.0,
                close=104.0,
                volume=1_000_000,
            ),
            MarketPrice(
                date=date(2025, 1, 15),
                open=103.0,
                high=108.0,
                low=102.0,
                close=107.0,
                volume=1_300_000,
            ),
        ]
        company = CompanyInfo(
            ticker="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            currency="USD",
        )

        mock_service = MagicMock(spec=MarketDataService)
        mock_service.get_ohlcv.return_value = prices
        mock_service.get_company_info.return_value = company

        agent = DataAgent(market_data_service=mock_service)
        result = asyncio.run(agent.analyze("aapl"))

        assert isinstance(result, DataAgentResult)
        assert result.ticker == "AAPL"
        assert result.company_info.company_name == "Apple Inc."
        assert result.records_count == 2
        assert result.start_date == date(2025, 1, 10)
        assert result.end_date == date(2025, 1, 15)
        assert len(result.price_history) == 2
        mock_service.get_ohlcv.assert_called_once()
        mock_service.get_company_info.assert_called_once_with("AAPL")

    def test_data_agent_rejects_empty_ticker(self):
        agent = DataAgent(market_data_service=MagicMock(spec=MarketDataService))
        with pytest.raises(MarketDataError, match="empty"):
            asyncio.run(agent.analyze("  "))

    def test_data_agent_normalizes_ticker(self):
        mock_service = MagicMock(spec=MarketDataService)
        mock_service.get_ohlcv.return_value = [
            MarketPrice(
                date=date(2025, 1, 10),
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=100,
            )
        ]
        mock_service.get_company_info.return_value = CompanyInfo(ticker="MSFT")

        agent = DataAgent(market_data_service=mock_service)
        result = asyncio.run(agent.analyze("msft"))

        assert result.ticker == "MSFT"
        called_ticker = mock_service.get_ohlcv.call_args[0][0]
        assert called_ticker == "MSFT"
