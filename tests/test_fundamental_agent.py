"""Tests for FundamentalAgent scoring from DataAgent snapshots."""

import asyncio
from datetime import date

from app.agents.fundamental_agent import FundamentalAgent
from app.models.schemas import (
    CompanyInfo,
    DataAgentResult,
    FundamentalSnapshot,
    MarketPrice,
)


def _data(fundamentals: FundamentalSnapshot) -> DataAgentResult:
    return DataAgentResult(
        ticker=fundamentals.ticker,
        company_info=CompanyInfo(ticker=fundamentals.ticker),
        price_history=[
            MarketPrice(
                date=date(2025, 1, 10),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1_000_000,
            )
        ],
        news=[],
        fundamentals=fundamentals,
        records_count=1,
    )


def test_bullish_from_strong_snapshot():
    snap = FundamentalSnapshot(
        ticker="SPY",
        quote_type="ETF",
        trailing_pe=16.0,
        forward_pe=15.0,
        ytd_return=0.12,
        three_year_avg_return=0.10,
        dividend_yield=0.015,
    )
    result = asyncio.run(FundamentalAgent().analyze("SPY", data=_data(snap)))
    assert result.agent_name == "fundamental_agent"
    assert result.signal == "bullish"
    assert result.confidence > 0
    assert "SPY" in result.explanation


def test_bearish_from_weak_snapshot():
    snap = FundamentalSnapshot(
        ticker="SPY",
        quote_type="ETF",
        trailing_pe=35.0,
        forward_pe=38.0,
        ytd_return=-0.10,
        three_year_avg_return=-0.05,
        debt_to_equity=250.0,
    )
    result = asyncio.run(FundamentalAgent().analyze("SPY", data=_data(snap)))
    assert result.signal == "bearish"


def test_empty_snapshot_is_unavailable():
    snap = FundamentalSnapshot(ticker="SPY", quote_type="ETF")
    result = asyncio.run(FundamentalAgent().analyze("SPY", data=_data(snap)))
    assert result.signal == "unavailable"
    assert result.confidence == 0.0


def test_missing_fundamentals_field_is_unavailable():
    data = DataAgentResult(
        ticker="SPY",
        company_info=CompanyInfo(ticker="SPY"),
        price_history=[],
        fundamentals=None,
        records_count=0,
    )
    result = asyncio.run(FundamentalAgent().analyze("SPY", data=data))
    assert result.signal == "unavailable"
