"""Tests for the FastAPI health endpoint and analyze API guards."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import FinalRecommendation

client = TestClient(app)


def test_health_returns_ok():
    """GET /health should return HTTP 200 with project info."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "project": "MarketMind",
    }


def _stub_coordinator(monkeypatch):
    """Make /analyze return instantly without market data or model calls."""

    async def fake_analyze(self, ticker, horizon_days=5):
        return FinalRecommendation(
            ticker=str(ticker).upper(),
            recommendation="HOLD",
            confidence=0.5,
            explanation="Stubbed decision.",
            horizon_days=horizon_days,
            agent_results=[],
        )

    monkeypatch.setattr(
        "app.main.CoordinatorAgent.analyze", fake_analyze, raising=True
    )


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    import app.main as main

    main._ANALYZE_HITS.clear()
    yield
    main._ANALYZE_HITS.clear()


def test_analyze_accepts_calls_within_the_rate_limit(monkeypatch):
    _stub_coordinator(monkeypatch)
    monkeypatch.setenv("ANALYZE_RATE_LIMIT", "2")
    monkeypatch.setenv("ANALYZE_RATE_WINDOW_SECONDS", "60")

    assert client.post("/analyze/AAPL").status_code == 200
    assert client.post("/analyze/AAPL").status_code == 200


def test_analyze_rate_limits_bursts(monkeypatch):
    _stub_coordinator(monkeypatch)
    monkeypatch.setenv("ANALYZE_RATE_LIMIT", "1")
    monkeypatch.setenv("ANALYZE_RATE_WINDOW_SECONDS", "60")

    assert client.post("/analyze/AAPL").status_code == 200
    response = client.post("/analyze/AAPL")
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1


def test_analyze_requires_demo_token_when_configured(monkeypatch):
    _stub_coordinator(monkeypatch)
    monkeypatch.setenv("ANALYZE_RATE_LIMIT", "0")  # disable rate limiting here
    monkeypatch.setenv("DEMO_API_TOKEN", "secret-token")

    assert client.post("/analyze/AAPL").status_code == 401
    ok = client.post("/analyze/AAPL", headers={"X-Demo-Token": "secret-token"})
    assert ok.status_code == 200
