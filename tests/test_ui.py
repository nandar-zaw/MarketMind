"""Tests for the Gradio UI formatting layer (no network, no real LLM).

A fake Coordinator returns a canned FinalRecommendation and a fake
DataAgent returns canned prices/company info, so analyze() output
shaping (panels, chart frame, company header) is deterministic.
"""

import asyncio
from datetime import date, timedelta

import pytest

import app.ui as ui
from app.models.schemas import (
    AgentResult,
    CompanyInfo,
    DataAgentResult,
    FinalRecommendation,
    MarketPrice,
)


def _prices(n=60):
    start = date(2026, 1, 1)
    return [
        MarketPrice(
            date=start + timedelta(days=i),
            open=100.0 + i * 0.1,
            high=101.0 + i * 0.1,
            low=99.0 + i * 0.1,
            close=100.0 + i * 0.1,
            volume=1_000_000,
        )
        for i in range(n)
    ]


def _final(ticker="AAPL"):
    return FinalRecommendation(
        ticker=ticker,
        recommendation="BUY",
        confidence=0.66,
        explanation="Canned final recommendation.",
        horizon_days=5,
        agent_results=[
            AgentResult(
                agent_name="fundamental_agent",
                signal="buy",
                confidence=0.7,
                explanation="Margins expanding.",
            ),
            AgentResult(
                agent_name="technical_agent",
                signal="bullish",
                confidence=0.8,
                explanation="Uptrend intact.",
            ),
            AgentResult(
                agent_name="sentiment_agent",
                signal="neutral",
                confidence=0.1,
                explanation="Mixed headlines.",
            ),
            AgentResult(
                agent_name="risk_agent",
                signal="medium",
                confidence=0.8,
                explanation="Moderate volatility.",
            ),
        ],
        guardrails=[],
    )


def _data(ticker="AAPL", n=60):
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
        records_count=n,
    )


class FakeCoordinator:
    async def analyze(self, ticker, horizon_days=5):
        return _final(ticker.upper())


class FakeDataAgent:
    def __init__(self, n=60):
        self._n = n

    async def analyze(self, ticker):
        return _data(ticker.upper(), n=self._n)


class BoomDataAgent:
    async def analyze(self, ticker):
        raise RuntimeError("provider down")


@pytest.fixture(autouse=True)
def _inject_fakes(monkeypatch):
    monkeypatch.setattr(ui, "_coordinator", FakeCoordinator())
    monkeypatch.setattr(ui, "_data_agent", FakeDataAgent())


def test_analyze_fills_panels_chart_and_company():
    out = asyncio.run(ui.analyze("AAPL", 5))
    assert len(out) == 18
    # Final panel first.
    assert out[0] == "🟢 BUY"
    assert out[1] == "0.66"
    # Agent panels carry badges.
    assert out[3] == "🟢 BUY"  # fundamental
    assert out[6] == "🟢 BULLISH"  # technical
    assert out[9] == "🟡 NEUTRAL"  # sentiment
    assert out[12] == "🟡 MEDIUM"  # risk
    # Chart frame: long format with all three series.
    chart = out[15]
    assert chart is not None
    assert set(chart["Series"].unique()) == {"Close", "SMA20", "SMA50"}
    # Full frame is kept in state for instant window re-filtering;
    # the default 6M window still covers this short fake history, so
    # the plot shows the same rows.
    assert out[17] is not None
    assert len(out[17]) == len(chart)
    # Company header.
    assert "Apple Inc." in out[16]
    assert "Technology" in out[16]
    assert "$3.20T" in out[16]


def test_visual_failure_keeps_recommendation_panels(monkeypatch):
    monkeypatch.setattr(ui, "_data_agent", BoomDataAgent())
    out = asyncio.run(ui.analyze("AAPL", 5))
    assert out[0] == "🟢 BUY"
    assert out[15] is None
    assert out[16] == ""
    assert out[17] is None


def test_coordinator_failure_surfaces_error_not_crash(monkeypatch):
    class BoomCoordinator:
        async def analyze(self, ticker, horizon_days=5):
            raise RuntimeError("kaboom")

    monkeypatch.setattr(ui, "_coordinator", BoomCoordinator())
    out = asyncio.run(ui.analyze("AAPL", 5))
    assert len(out) == 18
    assert "kaboom" in out[2]
    assert out[15] is None
    assert out[17] is None


def test_dashboard_runs_analysis_on_load():
    # The page must open populated: a load event runs analyze with
    # the ticker + horizon + window inputs and fills every output.
    deps = ui.demo.get_config_file()["dependencies"]
    loads = [d for d in deps if any(t[1] == "load" for t in d["targets"])]
    assert loads, "expected a page-load analysis to be wired"
    assert len(loads[0]["inputs"]) == 3
    assert len(loads[0]["outputs"]) == 18


def test_chart_window_filters_loaded_frame():
    import pandas as pd

    frame = ui._chart_frame(_data(n=400))
    filtered = ui._filter_chart(frame, "3M")
    assert filtered is not None and len(filtered) > 0
    assert len(filtered) < len(frame)
    dates = pd.to_datetime(filtered["date"])
    assert dates.max() == pd.to_datetime(frame["date"]).max()
    assert dates.min() >= dates.max() - pd.DateOffset(months=3)
    # 1Y and unknown windows leave the frame untouched.
    assert ui._filter_chart(frame, "1Y") is frame


def test_chart_frame_uses_weekly_points():
    import pandas as pd

    frame = ui._chart_frame(_data(n=400))
    dates = pd.to_datetime(frame["date"]).drop_duplicates().sort_values()
    # A year-plus of daily data collapses to roughly one point per
    # week, so the dates under the axis stay readable instead of
    # stacking into a strip.
    assert 40 <= len(dates) <= 90
    gaps = dates.diff().dropna().dt.days
    assert gaps.min() >= 3


def test_analyze_respects_selected_window(monkeypatch):
    monkeypatch.setattr(ui, "_data_agent", FakeDataAgent(n=400))
    out = asyncio.run(ui.analyze("AAPL", 5, window="3M"))
    # Plot shows the filtered slice; state keeps the full frame.
    assert len(out[15]) < len(out[17])
