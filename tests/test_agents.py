"""Tests for Risk Manager, Coordinator, schemas, and analyze endpoint.

All tests run offline: market data comes from a fake DataAgent, and the
OpenAI-backed Sentiment / Fundamental agents are replaced with stubs.
The real TechnicalAgent runs on the fake prices (it is pure math).
"""

import asyncio
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.agents.base_agent import BaseAgent
from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.data_agent import DataAgent
from app.agents.fundamental_agent import FundamentalAgent
from app.agents.risk_agent import RiskAgent
from app.agents.sentiment_agent import SentimentAgent
from app.agents.technical_agent import TechnicalAgent
from app.main import app
from app.models.schemas import (
    AgentResult,
    AnalysisRequest,
    CompanyInfo,
    DataAgentResult,
    MarketPrice,
)
from app.utils.exceptions import MarketDataError

client = TestClient(app)


def make_closes(n: int = 250, start: float = 100.0, daily_vol: float = 0.01, drift: float = 0.001, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return start * np.exp(np.cumsum(rng.normal(drift, daily_vol, n)))


def make_prices(n: int = 80, start: float = 100.0, daily_vol: float = 0.01, drift: float = 0.001) -> pd.DataFrame:
    close = make_closes(n, start, daily_vol, drift)
    return pd.DataFrame(
        {
            "Open": close * 0.99,
            "High": close * 1.01,
            "Low": close * 0.98,
            "Close": close,
            "Volume": np.full(n, 1_000_000),
        }
    )


def make_data(ticker: str = "AAPL", closes: np.ndarray | None = None) -> DataAgentResult:
    closes = make_closes() if closes is None else closes
    first_day = date(2025, 1, 2)
    bars = [
        MarketPrice(
            date=first_day + timedelta(days=i),
            open=float(c) * 0.99,
            high=float(c) * 1.01,
            low=float(c) * 0.98,
            close=float(c),
            volume=1_000_000,
        )
        for i, c in enumerate(closes)
    ]
    return DataAgentResult(
        ticker=ticker,
        company_info=CompanyInfo(ticker=ticker),
        price_history=bars,
        records_count=len(bars),
    )


class FakeDataAgent:
    """Stands in for DataAgent and counts how often it is asked for data."""

    def __init__(self, data: DataAgentResult | None = None, error: Exception | None = None):
        self.data = data
        self.error = error
        self.calls = 0

    async def analyze(self, ticker: str, **kwargs) -> DataAgentResult:
        self.calls += 1
        if self.error:
            raise self.error
        return self.data or make_data(ticker)


def stub_agent(name: str, signal: str, confidence: float = 0.8) -> BaseAgent:
    class Stub(BaseAgent):
        async def analyze(self, ticker: str):
            return AgentResult(
                agent_name=name,
                signal=signal,
                confidence=confidence,
                explanation=f"Stub {signal} result for {ticker}.",
            )

    stub = Stub()
    stub.name = name
    return stub


@pytest.fixture(autouse=True)
def offline_llm_agents(monkeypatch):
    """The real Sentiment and Fundamental agents call OpenAI."""

    async def fake_sentiment(self, ticker: str, *, data=None):
        return AgentResult(
            agent_name="sentiment_agent",
            signal="neutral",
            confidence=0.4,
            explanation="Offline test stub for the Sentiment agent.",
        )

    async def fake_fundamental(self, ticker: str, *, data=None):
        return AgentResult(
            agent_name="fundamental_agent",
            signal="hold",
            confidence=0.5,
            explanation="Offline test stub for the Fundamental agent.",
        )

    monkeypatch.setattr(SentimentAgent, "analyze", fake_sentiment)
    monkeypatch.setattr(FundamentalAgent, "analyze", fake_fundamental)


def test_agent_classes_exist():
    """All agent classes should be importable."""
    agents = [
        BaseAgent,
        DataAgent,
        TechnicalAgent,
        SentimentAgent,
        FundamentalAgent,
        RiskAgent,
        CoordinatorAgent,
    ]

    for agent_cls in agents:
        assert agent_cls is not None


def test_analysis_request_validation():
    request = AnalysisRequest(ticker="AAPL")
    assert request.ticker == "AAPL"
    assert request.horizon_days == 5


def test_analysis_request_custom_horizon():
    request = AnalysisRequest(ticker="MSFT", horizon_days=10)
    assert request.ticker == "MSFT"
    assert request.horizon_days == 10


def test_risk_agent_flags_high_volatility():
    prices = make_prices(daily_vol=0.05, drift=0.0)
    result = asyncio.run(RiskAgent().analyze("AAPL", price_history=prices))
    assert result.agent_name == "risk_agent"
    assert result.signal == "high"
    assert 0 <= result.confidence <= 1
    assert "volatility" in result.explanation.lower()


def test_risk_agent_flags_low_volatility():
    prices = make_prices(daily_vol=0.004, drift=0.0002)
    result = asyncio.run(RiskAgent().analyze("MSFT", price_history=prices))
    assert result.signal in {"low", "medium"}


def test_risk_level_uses_only_the_last_90_days():
    # A crash early in the year, then 90 calm days: the old crash must not count.
    crash = make_closes(160, start=100.0, daily_vol=0.01, drift=-0.006, seed=1)
    calm = make_closes(90, start=float(crash[-1]), daily_vol=0.004, drift=0.0003, seed=2)
    prices = pd.DataFrame({"Close": np.concatenate([crash, calm])})

    result = asyncio.run(RiskAgent().analyze("AAPL", price_history=prices))
    assert result.signal == "low"
    assert "last 90 trading days" in result.explanation
    assert "1-year baseline" in result.explanation


def test_risk_flags_volatility_spike_against_one_year_baseline():
    calm = make_closes(160, start=100.0, daily_vol=0.004, drift=0.0, seed=3)
    jumpy = make_closes(90, start=float(calm[-1]), daily_vol=0.02, drift=0.0, seed=4)
    prices = pd.DataFrame({"Close": np.concatenate([calm, jumpy])})

    result = asyncio.run(RiskAgent().analyze("TSLA", price_history=prices))
    assert result.signal == "high"
    assert "volatility spike" in result.explanation


def test_coordinator_fetches_data_once_and_shares_it():
    data_agent = FakeDataAgent()
    received = {}

    class RecordingSentiment(BaseAgent):
        name = "sentiment_agent"

        async def analyze(self, ticker: str, *, data=None):
            received["data"] = data
            return AgentResult(
                agent_name=self.name,
                signal="neutral",
                confidence=0.4,
                explanation="Recorded the shared data.",
            )

    coordinator = CoordinatorAgent(
        data_agent=data_agent,
        specialists={
            "technical_agent": TechnicalAgent(data_agent=data_agent),
            "sentiment_agent": RecordingSentiment(),
            "fundamental_agent": stub_agent("fundamental_agent", "hold"),
        },
    )
    result = asyncio.run(coordinator.analyze("aapl"))

    assert data_agent.calls == 1
    assert received["data"] is not None
    assert received["data"].ticker == "AAPL"
    technical = next(r for r in result.agent_results if r.agent_name == "technical_agent")
    assert technical.signal in {"bullish", "neutral", "bearish"}


def test_coordinator_uses_stub_specialists_and_risk():
    # Explicit stubs keep the "unavailable" path deterministic now that
    # all real specialists vote.
    coordinator = CoordinatorAgent(
        data_agent=FakeDataAgent(),
        specialists={
            "technical_agent": stub_agent("technical_agent", "bullish", 0.7),
            "sentiment_agent": stub_agent("sentiment_agent", "unavailable", 0.0),
            "fundamental_agent": stub_agent("fundamental_agent", "buy", 0.6),
        },
    )
    result = asyncio.run(coordinator.analyze("aapl"))
    assert result.ticker == "AAPL"
    assert result.recommendation in {"BUY", "HOLD", "SELL"}
    names = {item.agent_name for item in result.agent_results}
    assert {"technical_agent", "sentiment_agent", "fundamental_agent", "risk_agent"} <= names
    assert any(item.signal == "unavailable" for item in result.agent_results)
    assert "sentiment_agent" not in result.explanation
    assert any(event.kind == "input" for event in result.guardrails)
    assert any(event.kind == "tool" for event in result.guardrails)
    assert any(event.kind == "output" for event in result.guardrails)


def test_high_risk_cannot_stay_as_buy():
    jumpy = make_closes(250, daily_vol=0.06, drift=0.01)
    coordinator = CoordinatorAgent(
        data_agent=FakeDataAgent(make_data("NVDA", jumpy)),
        specialists={
            "technical_agent": stub_agent("technical_agent", "bullish", 0.9),
            "sentiment_agent": stub_agent("sentiment_agent", "bullish", 0.9),
            "fundamental_agent": stub_agent("fundamental_agent", "buy", 0.9),
        },
    )
    result = asyncio.run(coordinator.analyze("NVDA"))
    assert result.recommendation != "BUY"
    risk = next(item for item in result.agent_results if item.agent_name == "risk_agent")
    assert risk.signal == "high"


def test_fundamental_sell_vote_is_counted():
    coordinator = CoordinatorAgent(
        data_agent=FakeDataAgent(),
        specialists={"fundamental_agent": stub_agent("fundamental_agent", "sell")},
    )
    result = asyncio.run(coordinator.analyze("AAPL"))
    assert "fundamental_agent=sell" in result.explanation


def test_failing_specialist_becomes_unavailable():
    class BrokenStub(BaseAgent):
        name = "fundamental_agent"

        async def analyze(self, ticker: str):
            raise RuntimeError("FUNDAMENTALS_VECTOR_STORE_ID is not set.")

    coordinator = CoordinatorAgent(
        data_agent=FakeDataAgent(),
        specialists={"fundamental_agent": BrokenStub()},
    )
    result = asyncio.run(coordinator.analyze("AAPL"))
    fundamental = next(r for r in result.agent_results if r.agent_name == "fundamental_agent")
    assert fundamental.signal == "unavailable"
    assert "RuntimeError" in fundamental.explanation


def test_short_history_makes_technical_unavailable_not_a_crash():
    # 40 bars passes the Coordinator's 20-row check but is below SMA50's needs.
    data_agent = FakeDataAgent(make_data("AAPL", make_closes(40)))
    coordinator = CoordinatorAgent(
        data_agent=data_agent,
        specialists={"technical_agent": TechnicalAgent(data_agent=data_agent)},
    )
    result = asyncio.run(coordinator.analyze("AAPL"))
    technical = next(r for r in result.agent_results if r.agent_name == "technical_agent")
    assert technical.signal == "unavailable"
    assert "interim_5d_return" in result.explanation


def test_analyze_endpoint_rejects_bad_ticker():
    response = client.get("/analyze/not-a-ticker")
    assert response.status_code == 400
    body = response.json()
    assert body["guardrail_kind"] == "input"


def test_analyze_endpoint_reports_market_data_failure(monkeypatch):
    async def failing_data(self, ticker, **kwargs):
        raise MarketDataError("No price data found for ZZZZ.")

    monkeypatch.setattr(DataAgent, "analyze", failing_data)
    response = client.get("/analyze/ZZZZ")
    assert response.status_code == 400
    body = response.json()
    assert body["guardrail_kind"] == "tool"
    assert body["guardrail_name"] == "market_data_failure"


def test_analyze_endpoint_returns_recommendation(monkeypatch):
    async def fake_data(self, ticker, **kwargs):
        return make_data(ticker)

    monkeypatch.setattr(DataAgent, "analyze", fake_data)
    response = client.post("/analyze/AAPL")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["recommendation"] in {"BUY", "HOLD", "SELL"}
    assert "guardrails" in body
    assert len(body["agent_results"]) >= 4
