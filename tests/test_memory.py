"""Tests for Coordinator decision memory (offline, temporary SQLite file)."""

import asyncio
from datetime import date, datetime, timedelta, timezone

import numpy as np
from fastapi.testclient import TestClient

from app.agents.base_agent import BaseAgent
from app.agents.coordinator_agent import CoordinatorAgent
from app.main import app
from app.memory import DecisionMemory
from app.models.schemas import (
    AgentResult,
    CompanyInfo,
    DataAgentResult,
    FinalRecommendation,
    MarketPrice,
)

client = TestClient(app)


def make_data(ticker: str = "AAPL", n: int = 250) -> DataAgentResult:
    rng = np.random.default_rng(11)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.008, n)))
    bars = [
        MarketPrice(
            date=date(2025, 1, 2) + timedelta(days=i),
            open=float(c),
            high=float(c) * 1.01,
            low=float(c) * 0.99,
            close=float(c),
            volume=1_000_000,
        )
        for i, c in enumerate(closes)
    ]
    return DataAgentResult(
        ticker=ticker,
        company_info=CompanyInfo(ticker=ticker),
        price_history=bars,
        records_count=n,
    )


class FakeDataAgent:
    async def analyze(self, ticker: str, **kwargs) -> DataAgentResult:
        return make_data(ticker)


class SettableStub(BaseAgent):
    """A specialist whose vote the test can change between runs."""

    def __init__(self, name: str, signal: str):
        self.name = name
        self.signal = signal

    async def analyze(self, ticker: str):
        return AgentResult(
            agent_name=self.name,
            signal=self.signal,
            confidence=0.9,
            explanation=f"Stub {self.signal}.",
        )


def make_coordinator(memory: DecisionMemory, fundamental: SettableStub) -> CoordinatorAgent:
    return CoordinatorAgent(
        data_agent=FakeDataAgent(),
        specialists={
            "technical_agent": SettableStub("technical_agent", "neutral"),
            "fundamental_agent": fundamental,
        },
        memory=memory,
    )


def test_record_and_read_back(tmp_path):
    memory = DecisionMemory(tmp_path / "m.sqlite")
    final = FinalRecommendation(
        ticker="AAPL",
        recommendation="HOLD",
        confidence=0.6,
        explanation="test",
        agent_results=[
            AgentResult(agent_name="risk_agent", signal="medium", confidence=0.8, explanation="r"),
        ],
    )
    when = datetime(2026, 10, 5, 14, 0, tzinfo=timezone.utc)
    memory.record(final, last_close=250.5, analyzed_at=when)

    last = memory.last("aapl")
    assert last.recommendation == "HOLD"
    assert last.risk_level == "medium"
    assert last.last_close == 250.5
    assert last.analyzed_at == when
    assert memory.last("MSFT") is None


def test_first_analysis_is_noted(tmp_path):
    memory = DecisionMemory(tmp_path / "m.sqlite")
    coordinator = make_coordinator(memory, SettableStub("fundamental_agent", "hold"))

    result = asyncio.run(coordinator.analyze("AAPL"))

    assert result.previous_decision is None
    assert "first recorded analysis of AAPL" in result.explanation
    assert len(memory.history("AAPL")) == 1


def test_second_analysis_reports_what_changed(tmp_path):
    memory = DecisionMemory(tmp_path / "m.sqlite")
    fundamental = SettableStub("fundamental_agent", "hold")
    coordinator = make_coordinator(memory, fundamental)

    first = asyncio.run(coordinator.analyze("AAPL"))
    fundamental.signal = "sell"
    second = asyncio.run(coordinator.analyze("AAPL"))

    assert second.previous_decision is not None
    assert second.previous_decision.recommendation == first.recommendation
    assert "fundamental_agent hold->sell" in second.explanation
    assert [d.agent_signals["fundamental_agent"] for d in memory.history("AAPL")] == ["sell", "hold"]


def test_memory_failure_does_not_block_the_decision(tmp_path):
    class BrokenMemory(DecisionMemory):
        def last(self, ticker, horizon_days=None):
            raise OSError("disk full")

    coordinator = make_coordinator(
        BrokenMemory(tmp_path / "m.sqlite"), SettableStub("fundamental_agent", "hold")
    )
    result = asyncio.run(coordinator.analyze("AAPL"))
    assert result.recommendation in {"BUY", "HOLD", "SELL"}
    assert "Memory:" not in result.explanation


def test_history_endpoint_returns_saved_decisions():
    memory = DecisionMemory()  # path comes from the conftest temp file
    coordinator = make_coordinator(memory, SettableStub("fundamental_agent", "buy"))
    asyncio.run(coordinator.analyze("NVDA"))

    response = client.get("/history/nvda")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "NVDA"
    assert len(body["decisions"]) == 1
    assert body["decisions"][0]["agent_signals"]["fundamental_agent"] == "buy"


def test_history_endpoint_rejects_bad_ticker():
    response = client.get("/history/not-a-ticker")
    assert response.status_code == 400
    assert response.json()["guardrail_kind"] == "input"
