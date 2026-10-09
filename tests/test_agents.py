"""Tests for Risk Manager, Coordinator, schemas, and analyze endpoint."""

import asyncio

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.agents.base_agent import BaseAgent
from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.data_agent import DataAgent
from app.agents.fundamental_agent import FundamentalAgent
from app.agents.risk_agent import RiskAgent
from app.agents.sentiment_agent import SentimentAgent
from app.agents.technical_agent import TechnicalAgent
from app.main import app
from app.models.schemas import AgentResult, AnalysisRequest
from app.services.market_data import MarketDataService

client = TestClient(app)


def make_prices(n: int = 80, start: float = 100.0, daily_vol: float = 0.01, drift: float = 0.001) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    shocks = rng.normal(drift, daily_vol, n)
    close = start * np.exp(np.cumsum(shocks))
    return pd.DataFrame(
        {
            "Open": close * 0.99,
            "High": close * 1.01,
            "Low": close * 0.98,
            "Close": close,
            "Volume": np.full(n, 1_000_000),
        }
    )


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


def test_coordinator_uses_stub_specialists_and_risk():
    # Explicit specialist stubs (the test's name always promised
    # them): until now the real specialists ran here, and the
    # "unavailable" assertion below only passed while one of them
    # happened to be starved of data. Stubbing makes the degradation
    # path deterministic and keeps this test offline.
    class BullishStub(BaseAgent):
        name = "technical_agent"

        async def analyze(self, ticker: str):
            return AgentResult(
                agent_name=self.name,
                signal="bullish",
                confidence=0.7,
                explanation="Stub technicals.",
            )

    class UnavailableStub(BaseAgent):
        name = "sentiment_agent"

        async def analyze(self, ticker: str):
            return AgentResult(
                agent_name=self.name,
                signal="unavailable",
                confidence=0.0,
                explanation="Stub unavailable specialist.",
            )

    class BuyStub(BaseAgent):
        name = "fundamental_agent"

        async def analyze(self, ticker: str):
            return AgentResult(
                agent_name=self.name,
                signal="buy",
                confidence=0.6,
                explanation="Stub fundamentals.",
            )

    coordinator = CoordinatorAgent(
        price_fetcher=lambda **_: make_prices(daily_vol=0.008, drift=0.004),
        specialists={
            "technical_agent": BullishStub(),
            "sentiment_agent": UnavailableStub(),
            "fundamental_agent": BuyStub(),
        },
    )
    result = asyncio.run(coordinator.analyze("aapl"))
    assert result.ticker == "AAPL"
    assert result.recommendation in {"BUY", "HOLD", "SELL"}
    names = {item.agent_name for item in result.agent_results}
    assert {"technical_agent", "sentiment_agent", "fundamental_agent", "risk_agent"} <= names
    assert any(item.signal == "unavailable" for item in result.agent_results)
    assert any(event.kind == "input" for event in result.guardrails)
    assert any(event.kind == "tool" for event in result.guardrails)
    assert any(event.kind == "output" for event in result.guardrails)


def test_high_risk_cannot_stay_as_buy():
    class BullishStub(BaseAgent):
        name = "technical_agent"

        async def analyze(self, ticker: str):
            return AgentResult(
                agent_name=self.name,
                signal="bullish",
                confidence=0.9,
                explanation="Stub bullish technicals for a guardrail test.",
            )

    coordinator = CoordinatorAgent(
        price_fetcher=lambda **_: make_prices(daily_vol=0.06, drift=0.01),
        specialists={
            "technical_agent": BullishStub(),
            "sentiment_agent": SentimentAgent(),
            "fundamental_agent": FundamentalAgent(),
        },
    )
    result = asyncio.run(coordinator.analyze("NVDA"))
    assert result.recommendation != "BUY"
    risk = next(item for item in result.agent_results if item.agent_name == "risk_agent")
    assert risk.signal == "high"


def test_analyze_endpoint_rejects_bad_ticker():
    response = client.get("/analyze/not-a-ticker")
    assert response.status_code == 400
    body = response.json()
    assert body["guardrail_kind"] == "input"


def test_analyze_endpoint_returns_recommendation(monkeypatch):
    monkeypatch.setattr(
        MarketDataService,
        "get_price_history",
        lambda self, ticker, days=90: make_prices(drift=0.002, daily_vol=0.01),
    )
    response = client.post("/analyze/AAPL")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["recommendation"] in {"BUY", "HOLD", "SELL"}
    assert "guardrails" in body
    assert len(body["agent_results"]) >= 4
