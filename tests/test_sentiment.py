"""Tests for the SentimentAgent.

Uses a fake headline fetcher and a fake Runner so the scoring logic
is tested deterministically, without network or a real API key.
"""

import asyncio

import pytest

import app.agents.sentiment_agent as sentiment_module
from app.agents.sentiment_agent import SentimentAgent

HEADLINES = [
    {
        "title": "Company beats earnings estimates",
        "publisher": "Reuters",
        "published": "2026-10-04",
        "summary": "Profit rose.",
    },
    {
        "title": "Analysts raise price target",
        "publisher": "Bloomberg",
        "published": "2026-10-03",
        "summary": "",
    },
    {
        "title": "New product line announced",
        "publisher": "CNBC",
        "published": "2026-10-02",
        "summary": "",
    },
]


async def fake_fetcher(ticker):
    return list(HEADLINES)


class FakeResult:
    def __init__(self, text):
        self.final_output = text


class FakeRunner:
    """Stand-in for agents.Runner returning a canned final output."""

    text = ""

    @staticmethod
    async def run(agent, prompt):
        return FakeResult(FakeRunner.text)


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    sentiment_module._CACHE.clear()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(sentiment_module, "Runner", FakeRunner)
    FakeRunner.text = (
        "SCORE: 0.6\n"
        "EVIDENCE:\n"
        "- Strong earnings beat [1]\n"
        "VERDICT: Coverage leans positive."
    )


def test_bullish_from_positive_score():
    result = asyncio.run(
        SentimentAgent(headline_fetcher=fake_fetcher).analyze("AAPL")
    )
    assert result.signal == "bullish"
    assert result.confidence == 0.6
    assert "[1]" in result.explanation
    assert "3 recent headlines" in result.explanation


def test_neutral_band():
    FakeRunner.text = (
        "SCORE: 0.1\nEVIDENCE:\n- Mixed news [2]\nVERDICT: Little direction."
    )
    result = asyncio.run(
        SentimentAgent(headline_fetcher=fake_fetcher).analyze("MSFT")
    )
    assert result.signal == "neutral"
    assert result.confidence == 0.1


def test_score_is_clamped():
    FakeRunner.text = (
        "SCORE: -2.5\nEVIDENCE:\n- Bad news [1]\nVERDICT: Negative."
    )
    result = asyncio.run(
        SentimentAgent(headline_fetcher=fake_fetcher).analyze("TSLA")
    )
    assert result.signal == "bearish"
    assert result.confidence == 1.0


def test_unavailable_with_too_few_headlines():
    async def one_headline(ticker):
        return HEADLINES[:1]

    result = asyncio.run(
        SentimentAgent(headline_fetcher=one_headline).analyze("NVDA")
    )
    assert result.signal == "unavailable"
    assert result.confidence == 0.0


def test_fetch_failure_is_unavailable_not_crash():
    async def boom(ticker):
        raise RuntimeError("network down")

    result = asyncio.run(SentimentAgent(headline_fetcher=boom).analyze("AMZN"))
    assert result.signal == "unavailable"
    assert "network down" in result.explanation


def test_missing_api_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = asyncio.run(
        SentimentAgent(headline_fetcher=fake_fetcher).analyze("META")
    )
    assert result.signal == "unavailable"
