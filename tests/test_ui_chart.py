"""Tests for the Gradio price-history chart helpers."""

from datetime import date, timedelta

import pandas as pd

from app.models.schemas import CompanyInfo, DataAgentResult, MarketPrice
from app.ui import build_price_frame, plot_price_history


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
    assert len(fig.axes) == 1


def test_plot_handles_empty_frame():
    fig = plot_price_history(pd.DataFrame(), "1Y")
    assert fig is not None
