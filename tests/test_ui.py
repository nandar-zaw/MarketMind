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


def _data(ticker="AAPL"):
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
        price_history=_prices(),
        records_count=60,
    )


class FakeCoordinator:
    async def analyze(self, ticker, horizon_days=5):
        return _final(ticker.upper())


class FakeDataAgent:
    async def analyze(self, ticker):
        return _data(ticker.upper())


class BoomDataAgent:
    async def analyze(self, ticker):
        raise RuntimeError("provider down")


@pytest.fixture(autouse=True)
def _inject_fakes(monkeypatch):
    monkeypatch.setattr(ui, "_coordinator", FakeCoordinator())
    monkeypatch.setattr(ui, "_data_agent", FakeDataAgent())


def test_analyze_fills_panels_chart_and_company():
    out = asyncio.run(ui.analyze("AAPL", 5))
    assert len(out) == 17
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


def test_coordinator_failure_surfaces_error_not_crash(monkeypatch):
    class BoomCoordinator:
        async def analyze(self, ticker, horizon_days=5):
            raise RuntimeError("kaboom")

    monkeypatch.setattr(ui, "_coordinator", BoomCoordinator())
    out = asyncio.run(ui.analyze("AAPL", 5))
    assert len(out) == 17
    assert "kaboom" in out[2]
    assert out[15] is None
