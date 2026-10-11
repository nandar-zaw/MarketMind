"""
Smoke tests for the Gradio-only UI render helpers.

These guard against schema drift: the Gradio-only dashboard must render
from the same ``DataAgentResult`` (prices / news / SEC filings) that the
mounted UI uses. A regression here previously crashed every successful
analysis because the helper still read the removed ``fundamentals`` field.
"""

from datetime import date, timedelta

import pytest

from app.models.schemas import (
    CompanyInfo,
    DataAgentResult,
    FilingExcerpt,
    FinalRecommendation,
    MarketPrice,
)
from app.ui_gradio_only import (
    _idle_snapshot,
    _pipeline_html,
    _snapshot_html,
)


def _sample_data(n: int = 80, filings: int = 2) -> DataAgentResult:
    start = date(2025, 1, 2)
    prices = [
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
    return DataAgentResult(
        ticker="AAPL",
        company_info=CompanyInfo(ticker="AAPL", company_name="Apple Inc."),
        price_history=prices,
        news=[],
        filings=[
            FilingExcerpt(text=f"excerpt {i}", source=f"10-K {i}")
            for i in range(filings)
        ],
        records_count=n,
    )


def test_data_agent_result_has_no_fundamentals_field():
    """The live schema uses SEC filings, not a yfinance fundamentals snapshot."""
    assert "fundamentals" not in DataAgentResult.model_fields
    assert "filings" in DataAgentResult.model_fields


def test_snapshot_html_renders_without_fundamentals():
    html = _snapshot_html(_sample_data())
    assert "52-week range" in html
    assert "SEC filings" in html
    assert "2 excerpts" in html


def test_snapshot_html_handles_missing_filings():
    html = _snapshot_html(_sample_data(filings=0))
    assert "SEC filings" in html
    # Zero filings should not crash and should report none retrieved.
    assert "0 excerpts" in html or "none" in html


def test_pipeline_html_reports_filings_for_data_agent():
    html = _pipeline_html(None, _sample_data(filings=3))
    assert "SEC filings" in html
    assert "3" in html
    # Never references the removed field name.
    assert "fundamentals" not in html.lower()


def test_idle_snapshot_renders():
    html = _idle_snapshot()
    assert "SEC filings" in html


def test_full_render_path_after_recommendation():
    """Mirror the analyze() success path: pipeline + snapshot from one result."""
    data = _sample_data()
    final = FinalRecommendation(
        ticker="AAPL",
        recommendation="HOLD",
        confidence=0.5,
        explanation="Mixed signals.",
        horizon_days=5,
        agent_results=[],
    )
    pipeline = _pipeline_html(final, data)
    snapshot = _snapshot_html(data)
    assert "Agent pipeline" in pipeline
    assert "52-week range" in snapshot
