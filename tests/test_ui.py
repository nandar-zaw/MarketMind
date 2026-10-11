"""
Tests for the Gradio dashboard (no network, no real LLM).

The dashboard is the single mounted UI (`app/ui.py`). It renders from
the shared ``DataAgentResult`` the Coordinator already fetched (prices /
news / SEC filings) and draws its chart as plain SVG.

A fake Coordinator returns a canned FinalRecommendation, so the render
helpers (panels, KPI snapshot, pipeline, chart frame) stay deterministic.
"""

import asyncio
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import pytest

import app.ui as ui
from app.models.schemas import (
    CompanyInfo,
    DataAgentResult,
    FilingExcerpt,
    FinalRecommendation,
    MarketPrice,
)


def _prices(n: int = 80) -> list[MarketPrice]:
    start = date(2025, 1, 2)
    return [
        MarketPrice(
            date=start + timedelta(days=i),
            open=100.0 + i * 0.4,
            high=101.0 + i * 0.4,
            low=99.0 + i * 0.4,
            close=100.0 + i * 0.5,
            volume=1_000_000,
        )
        for i in range(n)
    ]


def _data(ticker: str = "AAPL", n: int = 80, filings: int = 2) -> DataAgentResult:
    return DataAgentResult(
        ticker=ticker,
        company_info=CompanyInfo(
            ticker=ticker,
            company_name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            exchange="NASDAQ",
            market_cap=3.2e12,
        ),
        price_history=_prices(n),
        news=[],
        filings=[
            FilingExcerpt(text=f"excerpt {i}", source=f"10-K {i}")
            for i in range(filings)
        ],
        records_count=n,
    )


def _final(ticker: str = "AAPL") -> FinalRecommendation:
    return FinalRecommendation(
        ticker=ticker,
        recommendation="HOLD",
        confidence=0.5,
        explanation="Mixed signals.",
        horizon_days=5,
        agent_results=[],
    )


_UNSET = object()


class FakeCoordinator:
    """Returns the decision plus the shared market data (one fetch)."""

    def __init__(self, data: Optional[DataAgentResult] = _UNSET):
        self._data = _data() if data is _UNSET else data

    async def run(self, ticker, horizon_days=5):
        return _final(ticker.upper()), self._data


class _OfflineMarketData:
    def get_intraday_ohlcv(self, symbol):
        raise RuntimeError("offline test: no intraday bars")


class _OfflineDataAgent:
    """Only used for the intraday side-chart; stays offline in tests."""

    def __init__(self):
        self.market_data = _OfflineMarketData()


@pytest.fixture(autouse=True)
def _inject_fakes(monkeypatch):
    monkeypatch.setattr(ui, "_coordinator", FakeCoordinator())
    monkeypatch.setattr(ui, "_data_agent", _OfflineDataAgent())


# --- schema / render helpers -------------------------------------------------

def test_data_agent_result_has_no_fundamentals_field():
    """The live schema uses SEC filings, not a yfinance fundamentals snapshot."""
    assert "fundamentals" not in DataAgentResult.model_fields
    assert "filings" in DataAgentResult.model_fields


def test_snapshot_html_renders_without_fundamentals():
    html = ui._snapshot_html(_data())
    assert "52-week range" in html
    assert "SEC filings" in html
    assert "2 excerpts" in html


def test_snapshot_html_handles_missing_filings():
    html = ui._snapshot_html(_data(filings=0))
    assert "SEC filings" in html
    assert "0 excerpts" in html or "none" in html


def test_pipeline_html_reports_filings_for_data_agent():
    html = ui._pipeline_html(None, _data(filings=3))
    assert "SEC filings" in html
    assert "3" in html
    assert "fundamentals" not in html.lower()


def test_idle_snapshot_renders():
    assert "SEC filings" in ui._idle_snapshot()


def test_full_render_path_after_recommendation():
    data = _data()
    pipeline = ui._pipeline_html(_final(), data)
    snapshot = ui._snapshot_html(data)
    assert "Agent pipeline" in pipeline
    assert "52-week range" in snapshot


# --- chart helpers -----------------------------------------------------------

def test_build_price_frame_has_close_and_moving_averages():
    frame = ui.build_price_frame(_data(n=400))
    assert {"date", "Price", "SMA20", "SMA50"} <= set(frame.columns)
    assert len(frame) == 400


def test_chart_window_slices_without_refetch():
    frame = ui.build_price_frame(_data(n=400))
    bundle = {"daily": frame, "intraday": pd.DataFrame()}
    one_year = ui.plot_price_history(bundle, "1Y")
    three_months = ui.plot_price_history(bundle, "3M")
    # Both are SVG strings; the 3M view is a subset of the 1Y data.
    assert isinstance(one_year, str) and "<svg" in one_year
    assert isinstance(three_months, str) and "<svg" in three_months


# --- analyze callback --------------------------------------------------------

def test_analyze_renders_decision_and_chart():
    out = asyncio.run(ui.analyze("AAPL", 5, "1Y"))
    assert len(out) == 10
    # Decision panel (HTML) reflects the canned HOLD.
    assert "HOLD" in out[2]
    # Chart is an SVG string, and the state bundle holds the daily frame.
    assert isinstance(out[5], str) and "<svg" in out[5]
    assert isinstance(out[6], dict) and "daily" in out[6]


def test_analyze_survives_coordinator_failure(monkeypatch):
    class BoomCoordinator:
        async def run(self, ticker, horizon_days=5):
            raise RuntimeError("kaboom")

    monkeypatch.setattr(ui, "_coordinator", BoomCoordinator())
    out = asyncio.run(ui.analyze("AAPL", 5, "1Y"))
    assert len(out) == 10
    # Error surfaces in the decision panel rather than crashing the page.
    assert "kaboom" in out[2]
    assert out[6] is None
