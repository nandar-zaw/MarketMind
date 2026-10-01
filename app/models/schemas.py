"""
Pydantic schemas for MarketMind requests and responses.

These models define the structured data shapes used across agents.
Phase 1 only defines the schemas — no real analysis yet.
"""

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    """Request to analyze a stock ticker."""

    ticker: str = Field(..., description="Stock ticker symbol, e.g. AAPL")
    horizon_days: int = Field(
        default=5,
        description="Prediction horizon in trading days",
    )


class AgentResult(BaseModel):
    """Structured output from a single specialized agent."""

    agent_name: str
    signal: str
    confidence: float
    explanation: str


class FinalRecommendation(BaseModel):
    """Final coordinated recommendation for a ticker."""

    ticker: str
    recommendation: str
    confidence: float
    explanation: str
    agent_results: list[AgentResult]
