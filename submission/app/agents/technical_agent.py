"""
Technical Analysis Agent.

Consumes historical OHLCV data from DataAgent and produces a simple
bullish / neutral / bearish technical signal with confidence and
a short human-readable explanation.

Does NOT download market data itself and does NOT emit BUY/HOLD/SELL.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from app.agents.base_agent import BaseAgent
from app.agents.data_agent import DataAgent
from app.models.schemas import (
    AgentResult,
    DataAgentResult,
    MarketPrice,
    TechnicalAnalysisResult,
)

logger = logging.getLogger(__name__)

# Minimum bars needed for SMA50 (also enough for RSI14 and MACD).
_MIN_BARS = 50
_RSI_PERIOD = 14
_SMA_FAST = 20
_SMA_SLOW = 50
_MACD_FAST = 12
_MACD_SLOW = 26
_MACD_SIGNAL = 9
_PRICE_LOOKBACK = 5
_VOLUME_MA = 20
# Relative tolerance used to treat two values as "approximately equal".
_EPS = 0.001
_PRICE_NEUTRAL_BAND = 0.005  # ±0.5% for the 5-day trend


class TechnicalAgent(BaseAgent):
    """
    Analyze RSI, SMA, MACD, volume, and short-term price trend.

    Indicator math is synchronous (pandas). analyze() stays async to
    match BaseAgent and so it can await DataAgent when needed.
    """

    name = "technical_agent"

    def __init__(self, data_agent: Optional[DataAgent] = None):
        self.data_agent = data_agent or DataAgent()

    async def analyze(
        self,
        ticker: str,
        *,
        data: Optional[DataAgentResult] = None,
    ) -> AgentResult:
        """
        Run technical analysis for a ticker.

        If ``data`` is not provided, obtain OHLCV via DataAgent
        (TechnicalAgent never calls yfinance directly).
        """
        if data is None:
            data = await self.data_agent.analyze(ticker)

        detail = self.analyze_prices(data.price_history)
        logger.info(
            "TechnicalAgent %s -> signal=%s score=%s confidence=%.2f",
            data.ticker,
            detail.signal,
            detail.score,
            detail.confidence,
        )
        return AgentResult(
            agent_name=self.name,
            signal=detail.signal,
            confidence=detail.confidence,
            explanation=detail.explanation,
        )

    def analyze_prices(
        self, price_history: list[MarketPrice]
    ) -> TechnicalAnalysisResult:
        """Pure technical analysis over a list of MarketPrice bars."""
        if len(price_history) < _MIN_BARS:
            raise ValueError(
                "Not enough historical data for technical analysis."
            )

        closes = pd.Series(
            [bar.close for bar in price_history], dtype=float
        )
        volumes = pd.Series(
            [bar.volume for bar in price_history], dtype=float
        )

        rsi = self.calculate_rsi(closes, period=_RSI_PERIOD)
        sma20 = self.calculate_sma(closes, window=_SMA_FAST)
        sma50 = self.calculate_sma(closes, window=_SMA_SLOW)
        macd_line, macd_signal = self.calculate_macd(closes)
        price_change_5d, price_vote = self.calculate_price_trend(
            closes, lookback=_PRICE_LOOKBACK
        )
        volume_trend = self.calculate_volume_trend(volumes)

        rsi_vote = self._rsi_vote(rsi)
        sma_vote = self._compare_vote(sma20, sma50)
        macd_vote = self._compare_vote(macd_line, macd_signal)

        votes = {
            "rsi": rsi_vote,
            "sma": sma_vote,
            "macd": macd_vote,
            "price": price_vote,
        }
        score = sum(votes.values())
        signal = self._score_to_signal(score)
        confidence = self._confidence(score, votes)
        explanation = self._build_explanation(
            signal=signal,
            rsi=rsi,
            sma20=sma20,
            sma50=sma50,
            macd=macd_line,
            macd_signal=macd_signal,
            price_change_5d=price_change_5d,
            volume_trend=volume_trend,
            votes=votes,
            score=score,
        )

        return TechnicalAnalysisResult(
            signal=signal,
            confidence=confidence,
            rsi=round(rsi, 2),
            sma20=round(sma20, 4),
            sma50=round(sma50, 4),
            macd=round(macd_line, 4),
            macd_signal=round(macd_signal, 4),
            price_change_5d=round(price_change_5d, 6),
            volume_trend=volume_trend,
            explanation=explanation,
            score=score,
        )

    # --- indicator calculations -------------------------------------------------

    def calculate_rsi(self, closes: pd.Series, period: int = 14) -> float:
        """
        Classic 14-period RSI using simple average gain / average loss.

        RSI = 100 - (100 / (1 + RS)), where RS = avg_gain / avg_loss.
        """
        delta = closes.diff()
        gains = delta.clip(lower=0)
        losses = (-delta).clip(lower=0)

        avg_gain = gains.rolling(window=period, min_periods=period).mean()
        avg_loss = losses.rolling(window=period, min_periods=period).mean()

        last_gain = float(avg_gain.iloc[-1])
        last_loss = float(avg_loss.iloc[-1])

        if last_loss == 0:
            return 100.0 if last_gain > 0 else 50.0

        rs = last_gain / last_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def calculate_sma(self, closes: pd.Series, window: int) -> float:
        """Return the latest simple moving average of ``window`` closes."""
        sma = closes.rolling(window=window, min_periods=window).mean()
        value = float(sma.iloc[-1])
        if pd.isna(value):
            raise ValueError(
                "Not enough historical data for technical analysis."
            )
        return value

    def calculate_macd(
        self, closes: pd.Series
    ) -> tuple[float, float]:
        """
        Standard MACD: EMA12 - EMA26, signal = EMA9 of MACD line.

        Returns (macd, signal) using the latest values.
        """
        ema_fast = closes.ewm(span=_MACD_FAST, adjust=False).mean()
        ema_slow = closes.ewm(span=_MACD_SLOW, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=_MACD_SIGNAL, adjust=False).mean()
        return float(macd_line.iloc[-1]), float(signal_line.iloc[-1])

    def calculate_price_trend(
        self, closes: pd.Series, lookback: int = 5
    ) -> tuple[float, int]:
        """
        Compare latest close to close ``lookback`` trading days earlier.

        Returns (fractional change, vote) where vote is +1 / 0 / -1.
        """
        if len(closes) <= lookback:
            raise ValueError(
                "Not enough historical data for technical analysis."
            )
        older = float(closes.iloc[-(lookback + 1)])
        latest = float(closes.iloc[-1])
        if older == 0:
            return 0.0, 0

        change = (latest - older) / older
        if change > _PRICE_NEUTRAL_BAND:
            vote = 1
        elif change < -_PRICE_NEUTRAL_BAND:
            vote = -1
        else:
            vote = 0
        return change, vote

    def calculate_volume_trend(self, volumes: pd.Series) -> str:
        """
        Compare latest volume to its 20-day average.

        Volume is supporting evidence only — never used in the score.
        """
        if volumes.isna().all() or (volumes <= 0).all():
            return "unavailable"
        if len(volumes) < _VOLUME_MA:
            return "unavailable"

        avg = float(volumes.rolling(window=_VOLUME_MA).mean().iloc[-1])
        latest = float(volumes.iloc[-1])
        if avg <= 0 or pd.isna(avg):
            return "unavailable"

        ratio = latest / avg
        if ratio > 1.1:
            return "above_average"
        if ratio < 0.9:
            return "below_average"
        return "normal"

    # --- scoring helpers --------------------------------------------------------

    @staticmethod
    def _rsi_vote(rsi: float) -> int:
        if rsi > 70:
            return -1  # overbought -> bearish consideration
        if rsi < 30:
            return 1  # oversold -> bullish consideration
        return 0

    @staticmethod
    def _compare_vote(left: float, right: float) -> int:
        """+1 if left clearly above right, -1 if clearly below, else 0."""
        if right == 0:
            if left > 0:
                return 1
            if left < 0:
                return -1
            return 0
        if left > right * (1 + _EPS):
            return 1
        if left < right * (1 - _EPS):
            return -1
        return 0

    @staticmethod
    def _score_to_signal(score: int) -> str:
        if score >= 2:
            return "bullish"
        if score <= -2:
            return "bearish"
        return "neutral"

    @staticmethod
    def _confidence(score: int, votes: dict[str, int]) -> float:
        """
        Transparent confidence from score strength + agreement.

        confidence = min(0.95, 0.45 + 0.125*|score| + 0.05*agreement_bonus)
        """
        if score == 0:
            agreement_bonus = 0
        else:
            sign = 1 if score > 0 else -1
            agreement_bonus = sum(
                1 for v in votes.values() if v != 0 and v == sign
            )
        value = 0.45 + 0.125 * abs(score) + 0.05 * agreement_bonus
        return round(min(0.95, value), 4)

    @staticmethod
    def _build_explanation(
        *,
        signal: str,
        rsi: float,
        sma20: float,
        sma50: float,
        macd: float,
        macd_signal: float,
        price_change_5d: float,
        volume_trend: str,
        votes: dict[str, int],
        score: int,
    ) -> str:
        """Build a short explanation from the indicator results (no LLM)."""
        parts = [
            f"The technical outlook is {signal} (score={score:+d}).",
            f"RSI(14) is {rsi:.1f}"
            + (
                " (overbought)."
                if votes["rsi"] < 0
                else " (oversold)."
                if votes["rsi"] > 0
                else " (neutral)."
            ),
            (
                f"SMA20 ({sma20:.2f}) is above SMA50 ({sma50:.2f})."
                if votes["sma"] > 0
                else f"SMA20 ({sma20:.2f}) is below SMA50 ({sma50:.2f})."
                if votes["sma"] < 0
                else f"SMA20 ({sma20:.2f}) and SMA50 ({sma50:.2f}) are roughly equal."
            ),
            (
                f"MACD ({macd:.4f}) is above its signal ({macd_signal:.4f})."
                if votes["macd"] > 0
                else f"MACD ({macd:.4f}) is below its signal ({macd_signal:.4f})."
                if votes["macd"] < 0
                else f"MACD ({macd:.4f}) is close to its signal ({macd_signal:.4f})."
            ),
            (
                f"Price rose {price_change_5d:.1%} over the last 5 trading days."
                if votes["price"] > 0
                else f"Price fell {price_change_5d:.1%} over the last 5 trading days."
                if votes["price"] < 0
                else f"Price changed {price_change_5d:.1%} over the last 5 trading days (small move)."
            ),
        ]
        if volume_trend != "unavailable":
            parts.append(f"Volume is {volume_trend.replace('_', ' ')}.")
        else:
            parts.append("Volume trend is unavailable.")
        return " ".join(parts)
