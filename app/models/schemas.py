"""
Pydantic schemas for MarketMind requests and responses.

These models define the structured data shapes used across agents.
"""

from datetime import date
from typing import Optional

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


class MarketPrice(BaseModel):
    """One daily OHLCV observation for a ticker."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: Optional[float] = None


class CompanyInfo(BaseModel):
    """Basic company metadata from the market data provider."""

    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    market_cap: Optional[float] = None


class NewsItem(BaseModel):
    """One recent news headline about a ticker."""

    title: str
    publisher: str = "Unknown source"
    published: Optional[str] = None  # ISO date (YYYY-MM-DD) when known
    summary: str = ""


class FilingExcerpt(BaseModel):
    """One retrieved passage from a company's SEC filings (10-K / 10-Q)."""

    text: str
    source: str = ""  # filing file name when known
    score: Optional[float] = None  # retrieval relevance score when provided


class DataAgentResult(BaseModel):
    """Structured output from the Data Collector Agent."""

    ticker: str
    company_info: CompanyInfo
    price_history: list[MarketPrice]
    news: list[NewsItem] = Field(default_factory=list)
    filings: list[FilingExcerpt] = Field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    records_count: int


class TechnicalAnalysisResult(BaseModel):
    """Detailed technical analysis from the Technical Agent."""

    signal: str  # bullish | neutral | bearish
    confidence: float  # 0.0 – 1.0
    rsi: float
    sma20: float
    sma50: float
    macd: float
    macd_signal: float
    price_change_5d: float  # fraction, e.g. 0.012 = +1.2%
    volume_trend: str  # above_average | normal | below_average | unavailable
    explanation: str
    score: int  # sum of indicator votes for transparency
