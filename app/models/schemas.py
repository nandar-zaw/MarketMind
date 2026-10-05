"""
Pydantic schemas for MarketMind requests and responses.

These models define the structured data shapes used across agents.
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


class GuardrailEvent(BaseModel):
    """Record of an input, tool, or output guardrail check."""

    kind: str = Field(..., description="input, tool, or output")
    name: str
    passed: bool
    detail: str


class FinalRecommendation(BaseModel):
    """Final coordinated recommendation for a ticker."""

    ticker: str
    recommendation: str
    confidence: float
    explanation: str
    horizon_days: int = 5
    agent_results: list[AgentResult]
    guardrails: list[GuardrailEvent] = Field(default_factory=list)
