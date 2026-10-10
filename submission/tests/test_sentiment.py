"""Tests for the SentimentAgent.

Uses a fake DataAgent (the documented data supplier) and a fake LLM
runner so the scoring logic is tested deterministically, without
network or a real API key.
"""

import asyncio

import pytest

from app.agents.sentiment_agent import SentimentAgent
from app.models.schemas import CompanyInfo, DataAgentResult, NewsItem


def _news(title, publisher="Reuters", published="2026-10-04", summary=""):
    return NewsItem(
        title=title, publisher=publisher, published=published, summary=summary
    )


HEADLINES = [
    _news("Company beats earnings estimates", summary="Profit rose."),
    _news("Analysts raise price target", publisher="Bloomberg", published="2026-10-03"),
    _news("New product line announced", publisher="CNBC", published="2026-10-02"),
]

BULLISH_TEXT = (
    "SCORE: 0.6\n"
    "EVIDENCE:\n"
    "- Strong earnings beat [1]\n"
    "VERDICT: Coverage leans positive."
)


def _data(ticker="AAPL", news=None):
    return DataAgentResult(
        ticker=ticker,
        company_info=CompanyInfo(ticker=ticker),
        price_history=[],
        news=list(HEADLINES if news is None else news),
        records_count=0,
    )


class FakeDataAgent:
    """Stands in for DataAgent: returns a canned DataAgentResult."""

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = []

    async def analyze(self, ticker):
        self.calls.append(ticker)
        if self._error is not None:
            raise self._error
        return self._result


def _runner(text):
    async def run(prompt):
        return text

    return run


def _agent(text=BULLISH_TEXT, data_agent=None):
    return SentimentAgent(
        data_agent=data_agent or FakeDataAgent(result=_data()),
        llm_runner=_runner(text),
    )


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_bullish_from_positive_score():
    result = asyncio.run(_agent().analyze("AAPL"))
    assert result.signal == "bullish"
    assert result.confidence == 0.6
    assert "[1]" in result.explanation
    assert "3 recent headlines" in result.explanation


def test_neutral_band():
    text = "SCORE: 0.1\nEVIDENCE:\n- Mixed news [2]\nVERDICT: Little direction."
    result = asyncio.run(_agent(text=text).analyze("MSFT"))
    assert result.signal == "neutral"
    assert result.confidence == 0.1


def test_score_is_clamped():
    text = "SCORE: -2.5\nEVIDENCE:\n- Bad news [1]\nVERDICT: Negative."
    result = asyncio.run(_agent(text=text).analyze("TSLA"))
    assert result.signal == "bearish"
    assert result.confidence == 1.0


def test_unavailable_with_too_few_headlines():
    data_agent = FakeDataAgent(result=_data(news=HEADLINES[:1]))
    result = asyncio.run(_agent(data_agent=data_agent).analyze("NVDA"))
    assert result.signal == "unavailable"
    assert result.confidence == 0.0


def test_data_failure_is_unavailable_not_crash():
    data_agent = FakeDataAgent(error=RuntimeError("network down"))
    result = asyncio.run(_agent(data_agent=data_agent).analyze("AMZN"))
    assert result.signal == "unavailable"
    assert "network down" in result.explanation


def test_missing_api_key_uses_keyword_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    agent = SentimentAgent(
        data_agent=FakeDataAgent(result=_data()),
        llm_runner=None,
    )
    result = asyncio.run(agent.analyze("META"))
    assert result.signal in {"bullish", "neutral", "bearish"}
    assert "keyword fallback" in result.explanation.lower()



def test_prefetched_data_skips_data_agent():
    # Mirrors TechnicalAgent: a supplied DataAgentResult is used
    # directly and the DataAgent is never called.
    exploding = FakeDataAgent(error=AssertionError("must not be called"))
    agent = SentimentAgent(data_agent=exploding, llm_runner=_runner(BULLISH_TEXT))
    result = asyncio.run(agent.analyze("AAPL", data=_data()))
    assert result.signal == "bullish"
    assert exploding.calls == []
