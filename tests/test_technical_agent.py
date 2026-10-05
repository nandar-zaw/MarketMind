"""
Unit tests for TechnicalAgent.

Uses synthetic OHLCV series — no live Yahoo Finance / network access.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.agents.technical_agent import TechnicalAgent
from app.models.schemas import MarketPrice, TechnicalAnalysisResult


def _make_prices(
    closes: list[float],
    start: date = date(2024, 1, 2),
    volume: int = 1_000_000,
) -> list[MarketPrice]:
    """Build MarketPrice rows from a close series (OHLC ≈ close)."""
    prices: list[MarketPrice] = []
    day = start
    for close in closes:
        # Skip weekends for slightly more realistic dating (optional).
        while day.weekday() >= 5:
            day += timedelta(days=1)
        prices.append(
            MarketPrice(
                date=day,
                open=close * 0.99,
                high=close * 1.01,
                low=close * 0.98,
                close=close,
                volume=volume,
            )
        )
        day += timedelta(days=1)
    return prices


def _rising_closes(n: int = 80, start: float = 100.0, step: float = 1.0) -> list[float]:
    return [start + i * step for i in range(n)]


def _falling_closes(n: int = 80, start: float = 200.0, step: float = 1.0) -> list[float]:
    return [start - i * step for i in range(n)]


def _flat_closes(n: int = 80, level: float = 100.0) -> list[float]:
    return [level] * n


class TestTechnicalIndicators:
    def test_rsi_produces_valid_result(self):
        agent = TechnicalAgent()
        closes = pd.Series(_rising_closes(60), dtype=float)
        rsi = agent.calculate_rsi(closes, period=14)
        assert 0.0 <= rsi <= 100.0
        # Strong uptrend should push RSI above the midpoint.
        assert rsi > 50.0

    def test_sma20_and_sma50_are_calculated(self):
        agent = TechnicalAgent()
        closes = pd.Series(_rising_closes(60), dtype=float)
        sma20 = agent.calculate_sma(closes, window=20)
        sma50 = agent.calculate_sma(closes, window=50)
        assert sma20 > 0
        assert sma50 > 0
        # In a steady uptrend, the faster SMA sits above the slower one.
        assert sma20 > sma50

    def test_macd_and_signal_are_calculated(self):
        agent = TechnicalAgent()
        closes = pd.Series(_rising_closes(60), dtype=float)
        macd, signal = agent.calculate_macd(closes)
        assert isinstance(macd, float)
        assert isinstance(signal, float)
        # Rising market: MACD typically above signal after a sustained trend.
        assert macd > signal

    def test_five_day_price_change_is_calculated(self):
        agent = TechnicalAgent()
        closes = pd.Series(_rising_closes(60, step=2.0), dtype=float)
        change, vote = agent.calculate_price_trend(closes, lookback=5)
        assert change > 0
        assert vote == 1


class TestTechnicalSignals:
    def test_bullish_data_produces_bullish_result(self):
        agent = TechnicalAgent()
        prices = _make_prices(_rising_closes(80, step=1.5))
        result = agent.analyze_prices(prices)
        assert isinstance(result, TechnicalAnalysisResult)
        assert result.signal == "bullish"
        assert result.score >= 2
        assert 0.0 <= result.confidence <= 1.0
        assert "bullish" in result.explanation.lower()

    def test_bearish_data_produces_bearish_result(self):
        agent = TechnicalAgent()
        prices = _make_prices(_falling_closes(80, step=1.5))
        result = agent.analyze_prices(prices)
        assert result.signal == "bearish"
        assert result.score <= -2
        assert "bearish" in result.explanation.lower()

    def test_mixed_indicators_can_produce_neutral(self):
        agent = TechnicalAgent()
        # Flat prices -> RSI ~50, SMA equal, MACD near 0, tiny 5-day change.
        prices = _make_prices(_flat_closes(80))
        result = agent.analyze_prices(prices)
        assert result.signal == "neutral"
        assert -1 <= result.score <= 1

    def test_insufficient_historical_data_is_handled(self):
        agent = TechnicalAgent()
        prices = _make_prices(_rising_closes(30))
        with pytest.raises(ValueError, match="Not enough historical data"):
            agent.analyze_prices(prices)

    def test_volume_trend_labels(self):
        agent = TechnicalAgent()
        volumes = pd.Series([1_000_000] * 25 + [2_000_000], dtype=float)
        assert agent.calculate_volume_trend(volumes) == "above_average"

        volumes_low = pd.Series([1_000_000] * 25 + [500_000], dtype=float)
        assert agent.calculate_volume_trend(volumes_low) == "below_average"

        volumes_zero = pd.Series([0.0] * 30, dtype=float)
        assert agent.calculate_volume_trend(volumes_zero) == "unavailable"
