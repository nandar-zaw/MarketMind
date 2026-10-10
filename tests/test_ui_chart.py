"""Tests for the Gradio price-history chart helpers."""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.models.schemas import CompanyInfo, DataAgentResult, MarketPrice
from app.services.market_data import MarketDataService
from app.ui import (
    UI_TICKER_CHOICES,
    build_intraday_frame,
    build_price_frame,
    plot_price_history,
)
from app.utils.exceptions import MarketDataError


def _sample_data(n: int = 80) -> DataAgentResult:
    start = date(2025, 1, 2)
    prices = []
    for i in range(n):
        close = 100.0 + i * 0.5
        prices.append(
            MarketPrice(
                date=start + timedelta(days=i),
                open=close - 0.2,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=1_000_000,
            )
        )
    return DataAgentResult(
        ticker="SPY",
        company_info=CompanyInfo(ticker="SPY"),
        price_history=prices,
        records_count=n,
    )


def _sample_intraday_raw(n: int = 60) -> pd.DataFrame:
    index = pd.date_range("2025-01-15 09:30", periods=n, freq="5min")
    close = pd.Series([100 + i * 0.05 for i in range(n)], index=index)
    return pd.DataFrame(
        {
            "Open": close - 0.1,
            "High": close + 0.2,
            "Low": close - 0.2,
            "Close": close,
            "Volume": 10_000,
        },
        index=index,
    )


def test_ui_ticker_choices_include_common_symbols():
    assert "SPY" in UI_TICKER_CHOICES
    assert "QQQ" in UI_TICKER_CHOICES
    assert "NVDA" in UI_TICKER_CHOICES
    assert "TSLA" in UI_TICKER_CHOICES
    assert "AAPL" in UI_TICKER_CHOICES


def test_build_price_frame_includes_sma_columns():
    frame = build_price_frame(_sample_data())
    assert list(frame.columns) == ["date", "Price", "SMA20", "SMA50"]
    assert len(frame) == 80
    assert frame["SMA20"].notna().sum() == 80 - 19
    assert frame["SMA50"].notna().sum() == 80 - 49


def test_plot_price_history_returns_figure():
    frame = build_price_frame(_sample_data())
    fig = plot_price_history(frame, "3M")
    assert fig is not None
    names = {trace.name for trace in fig.data}
    assert {"Close", "SMA20", "SMA50"} <= names


def test_plot_handles_empty_frame():
    fig = plot_price_history(pd.DataFrame(), "1Y")
    assert fig is not None


def test_plot_daily_1d_uses_intraday_bundle():
    daily = build_price_frame(_sample_data())
    intraday = build_intraday_frame(_sample_intraday_raw())
    fig = plot_price_history({"daily": daily, "intraday": intraday}, "1D")
    assert fig is not None
    assert "1D" in fig.layout.title.text
    assert len(fig.data[1].x) == len(intraday)


def test_plot_5d_uses_daily_closes():
    daily = build_price_frame(_sample_data())
    intraday = build_intraday_frame(_sample_intraday_raw())
    fig = plot_price_history({"daily": daily, "intraday": intraday}, "5D")
    assert fig is not None
    assert "5D" in fig.layout.title.text
    assert len(fig.data[1].x) == 5


def test_get_intraday_ohlcv_maps_provider_frame():
    service = MarketDataService()
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _sample_intraday_raw()

    with patch("app.services.market_data.yf.Ticker", return_value=mock_ticker):
        frame = service.get_intraday_ohlcv("spy")

    mock_ticker.history.assert_called_with(period="1d", interval="5m")
    assert not frame.empty
    assert "Close" in frame.columns


def test_get_intraday_empty_raises():
    service = MarketDataService()
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()

    with patch("app.services.market_data.yf.Ticker", return_value=mock_ticker):
        with pytest.raises(MarketDataError, match="No intraday"):
            service.get_intraday_ohlcv("SPY")
