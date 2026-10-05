"""Tests for the CoordinatorAgent weighted-scoring protocol.

Uses fake specialists so the scoring math is tested deterministically
without any LLM or API key.
"""

import asyncio

from app.agents.base_agent import BaseAgent
from app.agents.coordinator_agent import CoordinatorAgent
from app.models.schemas import AgentResult


class FakeAgent(BaseAgent):
    """Specialist stub returning a canned AgentResult."""

    def __init__(self, name: str, signal: str, confidence: float):
        self.name = name
        self._result = AgentResult(
            agent_name=name,
            signal=signal,
            confidence=confidence,
            explanation="fake",
        )

    async def analyze(self, ticker: str) -> AgentResult:
        return self._result


class FailingAgent(BaseAgent):
    """Specialist stub that always raises (like a placeholder)."""

    name = "failing_agent"

    async def analyze(self, ticker: str) -> AgentResult:
        raise NotImplementedError("not implemented yet")


def test_single_buy_gives_buy():
    coordinator = CoordinatorAgent(
        specialists=[FakeAgent("fundamental_agent", "buy", 0.9)]
    )
    rec = asyncio.run(coordinator.analyze("AAPL"))
    assert rec.recommendation == "buy"
    assert rec.confidence == 0.9
    assert len(rec.agent_results) == 1


def test_unavailable_agents_are_skipped():
    coordinator = CoordinatorAgent(
        specialists=[
            FakeAgent("fundamental_agent", "sell", 0.8),
            FailingAgent(),
        ]
    )
    rec = asyncio.run(coordinator.analyze("TSLA"))
    assert rec.recommendation == "sell"
    assert rec.confidence == 0.8
    assert "1 unavailable" in rec.explanation


def test_no_agents_holds_with_zero_confidence():
    coordinator = CoordinatorAgent(specialists=[FailingAgent()])
    rec = asyncio.run(coordinator.analyze("AAPL"))
    assert rec.recommendation == "hold"
    assert rec.confidence == 0.0
    assert rec.agent_results == []


def test_weights_renormalize_over_available_agents():
    # fundamental 0.40 vs technical 0.35, sentiment absent.
    # score = 0.40/(0.75)*(+0.6) + 0.35/(0.75)*(-1.0) = 0.32 - 0.4667 = -0.1467 -> hold
    coordinator = CoordinatorAgent(
        specialists=[
            FakeAgent("fundamental_agent", "buy", 0.6),
            FakeAgent("technical_agent", "sell", 1.0),
        ]
    )
    rec = asyncio.run(coordinator.analyze("AAPL"))
    assert rec.recommendation == "hold"
    assert rec.confidence == 0.15


def test_unknown_signal_counts_as_neutral():
    coordinator = CoordinatorAgent(
        specialists=[FakeAgent("fundamental_agent", "strong-buy", 0.9)]
    )
    rec = asyncio.run(coordinator.analyze("AAPL"))
    assert rec.recommendation == "hold"
    assert rec.confidence == 0.0
