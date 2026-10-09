"""Tests for the Fundamental Analysis Agent (no network, no real LLM).

A fake DataAgent supplies canned DataAgentResult values (including
SEC filing excerpts) and a fake llm_runner returns canned model
output, mirroring tests/test_sentiment.py.
"""

import asyncio

import pytest

from app.agents.fundamental_agent import FundamentalAgent
from app.models.schemas import (
    CompanyInfo,
    DataAgentResult,
    FilingExcerpt,
)


def _excerpts(n=3):
    texts = [
        "Revenue grew 12% year over year to $99.1B; gross margin expanded to 46.9%.",
        "Cash and marketable securities totaled $146.5B against $132.4B of total debt.",
        "Risk factors include supply constraints, tariffs, and foreign exchange volatility.",
    ]
    return [
        FilingExcerpt(text=texts[i % len(texts)], source="AAPL_10-K.txt", score=0.9)
        for i in range(n)
    ]


def _data(ticker="AAPL", filings=None):
    return DataAgentResult(
        ticker=ticker,
        company_info=CompanyInfo(ticker=ticker, company_name="Apple Inc."),
        price_history=[],
        filings=_excerpts() if filings is None else filings,
        records_count=0,
    )


class FakeDataAgent:
    def __init__(self, filings=None):
        self._filings = filings
        self.calls = []

    async def analyze(self, ticker):
        self.calls.append(ticker)
        return _data(ticker.upper(), filings=self._filings)


def _runner(output, capture=None):
    async def run(prompt):
        if capture is not None:
            capture.append(prompt)
        return output

    return run


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_scores_supplied_filing_evidence():
    captured = []
    agent = FundamentalAgent(
        llm_runner=_runner(
            "SCORE: 0.8\n"
            "EVIDENCE:\n"
            "- Revenue grew 12% with margin expansion [1]\n"
            "- Cash of $146.5B exceeds total debt [2]\n"
            "VERDICT: Fundamentally strong.",
            capture=captured,
        )
    )
    result = asyncio.run(agent.analyze("AAPL", data=_data()))
    assert result.signal == "buy"
    assert result.confidence == 0.8
    assert result.explanation.startswith(
        "Fundamentals from 3 SEC filing excerpts for AAPL:"
    )
    assert "Fundamentally strong." in result.explanation
    # Excerpts are injected numbered, with sources.
    assert "[1] (source: AAPL_10-K.txt)" in captured[0]


def test_negative_score_is_sell_and_small_score_is_hold():
    bearish = FundamentalAgent(
        llm_runner=_runner("SCORE: -0.6\nEVIDENCE:\n- Debt rising [1]\nVERDICT: Weak.")
    )
    result = asyncio.run(bearish.analyze("AAPL", data=_data()))
    assert result.signal == "sell"
    assert result.confidence == 0.6

    neutral = FundamentalAgent(
        llm_runner=_runner("SCORE: 0.1\nEVIDENCE:\n- Mixed [1]\nVERDICT: Mixed.")
    )
    result = asyncio.run(neutral.analyze("AAPL", data=_data()))
    assert result.signal == "hold"
    assert result.confidence == 0.1


def test_no_filing_evidence_is_unavailable_not_a_crash():
    agent = FundamentalAgent(llm_runner=_runner("SCORE: 0.9"))
    result = asyncio.run(agent.analyze("AAPL", data=_data(filings=[])))
    assert result.signal == "unavailable"
    assert result.confidence == 0.0


def test_fetches_through_data_agent_when_no_data_passed():
    fake = FakeDataAgent()
    agent = FundamentalAgent(
        data_agent=fake,
        llm_runner=_runner("SCORE: 0.5\nEVIDENCE:\n- Growth [1]\nVERDICT: Solid."),
    )
    result = asyncio.run(agent.analyze("aapl"))
    assert fake.calls == ["aapl"]
    assert result.signal == "buy"


def test_missing_api_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    agent = FundamentalAgent(llm_runner=_runner("SCORE: 0.9"))
    result = asyncio.run(agent.analyze("AAPL", data=_data()))
    assert result.signal == "unavailable"
    assert result.confidence == 0.0


def test_llm_failure_is_unavailable():
    async def boom(prompt):
        raise RuntimeError("model down")

    agent = FundamentalAgent(llm_runner=boom)
    result = asyncio.run(agent.analyze("AAPL", data=_data()))
    assert result.signal == "unavailable"
    assert "model down" in result.explanation


def test_unparseable_output_holds_with_zero_confidence():
    agent = FundamentalAgent(llm_runner=_runner("The company looks fine overall."))
    result = asyncio.run(agent.analyze("AAPL", data=_data()))
    assert result.signal == "hold"
    assert result.confidence == 0.0
