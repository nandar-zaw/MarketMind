"""Tests for agent placeholders, schemas, and analyze endpoint."""

from fastapi.testclient import TestClient

from app.agents.base_agent import BaseAgent
from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.data_agent import DataAgent
from app.agents.fundamental_agent import FundamentalAgent
from app.agents.risk_agent import RiskAgent
from app.agents.sentiment_agent import SentimentAgent
from app.agents.technical_agent import TechnicalAgent
from app.main import app
from app.models.schemas import AnalysisRequest

client = TestClient(app)


def test_agent_classes_exist():
    """All Phase 1 agent placeholder classes should be importable."""
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
    """AnalysisRequest should validate ticker and default horizon."""
    request = AnalysisRequest(ticker="AAPL")

    assert request.ticker == "AAPL"
    assert request.horizon_days == 5


def test_analysis_request_custom_horizon():
    """AnalysisRequest should accept a custom horizon_days value."""
    request = AnalysisRequest(ticker="MSFT", horizon_days=10)

    assert request.ticker == "MSFT"
    assert request.horizon_days == 10


def test_analyze_endpoint_returns_501():
    """POST /analyze/{ticker} should return HTTP 501 in Phase 1."""
    response = client.post("/analyze/AAPL")

    assert response.status_code == 501
    body = response.json()
    assert "later phase" in body["detail"].lower()
    assert body["ticker"] == "AAPL"
