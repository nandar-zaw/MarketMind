"""
Fundamental Analysis Agent.

Scores valuation / growth / quality from the FundamentalSnapshot that
DataAgent fetches via yfinance (direct API). No SEC file storage is
required for the S&P 500 (SPY) path.

Optional legacy: if FUNDAMENTALS_VECTOR_STORE_ID is set, teammates can
still experiment with SEC RAG later — the default classroom path is
the DataAgent snapshot.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.agents.base_agent import BaseAgent
from app.agents.data_agent import DataAgent
from app.models.schemas import AgentResult, DataAgentResult, FundamentalSnapshot

logger = logging.getLogger(__name__)

_AGENT_NAME = "fundamental_agent"
_BULLISH_THRESHOLD = 2
_BEARISH_THRESHOLD = -2


class FundamentalAgent(BaseAgent):
    """Fundamental analysis from DataAgent market-API metrics."""

    name = _AGENT_NAME

    def __init__(self, data_agent: Optional[DataAgent] = None):
        self.data_agent = data_agent or DataAgent()

    async def analyze(
        self,
        ticker: str,
        *,
        data: Optional[DataAgentResult] = None,
    ) -> AgentResult:
        """
        Score fundamentals for a ticker.

        Prefer the shared DataAgentResult from the Coordinator. If none
        is passed, fetch via DataAgent (never via SEC file storage).
        """
        if data is None:
            try:
                data = await self.data_agent.analyze(ticker)
            except Exception as exc:
                return AgentResult(
                    agent_name=self.name,
                    signal="unavailable",
                    confidence=0.0,
                    explanation=(
                        f"Could not retrieve fundamentals for "
                        f"{str(ticker).upper()} ({type(exc).__name__}: {exc})."
                    ),
                )

        snapshot = data.fundamentals
        if snapshot is None:
            return AgentResult(
                agent_name=self.name,
                signal="unavailable",
                confidence=0.0,
                explanation=(
                    f"No fundamental snapshot available for {data.ticker}, "
                    "so this agent does not vote."
                ),
            )

        signal, confidence, explanation = _score_snapshot(snapshot)
        logger.info(
            "FundamentalAgent %s -> signal=%s confidence=%.2f",
            data.ticker,
            signal,
            confidence,
        )
        return AgentResult(
            agent_name=self.name,
            signal=signal,
            confidence=confidence,
            explanation=explanation,
        )


def _score_snapshot(
    snap: FundamentalSnapshot,
) -> tuple[str, float, str]:
    """
    Turn a FundamentalSnapshot into bullish / neutral / bearish.

    Each available metric casts a simple vote (+1 / 0 / -1). Enough for
    a classroom demo; the Fundamental teammate can refine later.
    """
    votes: list[tuple[str, int]] = []

    # Valuation: lower trailing P/E tends to look more attractive.
    if snap.trailing_pe is not None:
        if snap.trailing_pe < 18:
            votes.append((f"trailing P/E {snap.trailing_pe:.1f} looks inexpensive", 1))
        elif snap.trailing_pe > 28:
            votes.append((f"trailing P/E {snap.trailing_pe:.1f} looks expensive", -1))
        else:
            votes.append((f"trailing P/E {snap.trailing_pe:.1f} is moderate", 0))

    # Forward vs trailing: cheaper forward implies expected earnings growth.
    if snap.forward_pe is not None and snap.trailing_pe is not None:
        if snap.forward_pe < snap.trailing_pe * 0.95:
            votes.append(
                (
                    f"forward P/E {snap.forward_pe:.1f} below trailing "
                    f"{snap.trailing_pe:.1f}",
                    1,
                )
            )
        elif snap.forward_pe > snap.trailing_pe * 1.05:
            votes.append(
                (
                    f"forward P/E {snap.forward_pe:.1f} above trailing "
                    f"{snap.trailing_pe:.1f}",
                    -1,
                )
            )

    if snap.revenue_growth is not None:
        if snap.revenue_growth > 0.03:
            votes.append((f"revenue growth {snap.revenue_growth:.1%}", 1))
        elif snap.revenue_growth < -0.03:
            votes.append((f"revenue growth {snap.revenue_growth:.1%}", -1))
        else:
            votes.append((f"revenue growth {snap.revenue_growth:.1%} flat", 0))

    if snap.earnings_growth is not None:
        if snap.earnings_growth > 0.03:
            votes.append((f"earnings growth {snap.earnings_growth:.1%}", 1))
        elif snap.earnings_growth < -0.03:
            votes.append((f"earnings growth {snap.earnings_growth:.1%}", -1))

    if snap.profit_margins is not None:
        if snap.profit_margins > 0.15:
            votes.append((f"profit margin {snap.profit_margins:.1%} is strong", 1))
        elif snap.profit_margins < 0.05:
            votes.append((f"profit margin {snap.profit_margins:.1%} is weak", -1))

    if snap.debt_to_equity is not None:
        if snap.debt_to_equity > 200:
            votes.append((f"debt/equity {snap.debt_to_equity:.0f} is elevated", -1))
        elif snap.debt_to_equity < 80:
            votes.append((f"debt/equity {snap.debt_to_equity:.0f} looks manageable", 1))

    # ETF / index friendly signals (SPY often has these).
    if snap.ytd_return is not None:
        if snap.ytd_return > 0.05:
            votes.append((f"YTD return {snap.ytd_return:.1%}", 1))
        elif snap.ytd_return < -0.05:
            votes.append((f"YTD return {snap.ytd_return:.1%}", -1))
        else:
            votes.append((f"YTD return {snap.ytd_return:.1%} is muted", 0))

    if snap.three_year_avg_return is not None:
        if snap.three_year_avg_return > 0.08:
            votes.append(
                (f"3Y avg return {snap.three_year_avg_return:.1%} is solid", 1)
            )
        elif snap.three_year_avg_return < 0.0:
            votes.append(
                (f"3Y avg return {snap.three_year_avg_return:.1%} is weak", -1)
            )

    if snap.dividend_yield is not None and snap.dividend_yield > 0:
        votes.append((f"dividend yield {snap.dividend_yield:.2%}", 0))

    if not votes:
        return (
            "unavailable",
            0.0,
            (
                f"Fundamental snapshot for {snap.ticker} has no usable metrics "
                f"(quote_type={snap.quote_type}), so this agent does not vote."
            ),
        )

    score = sum(v for _, v in votes)
    if score >= _BULLISH_THRESHOLD:
        signal = "bullish"
    elif score <= _BEARISH_THRESHOLD:
        signal = "bearish"
    else:
        signal = "neutral"

    agreeing = sum(1 for _, v in votes if (v > 0 and score > 0) or (v < 0 and score < 0) or score == 0)
    confidence = round(min(0.95, 0.4 + 0.15 * abs(score) + 0.05 * agreeing), 2)

    bullets = "; ".join(reason for reason, _ in votes[:6])
    quote = snap.quote_type or "unknown"
    explanation = (
        f"Fundamental outlook for {snap.ticker} ({quote}) is {signal} "
        f"(score={score:+d}). {bullets}."
    )
    return signal, confidence, explanation
