"""
Risk Manager Agent.

Job: measure how dangerous the recent price path is, then report a
LOW / MEDIUM / HIGH risk level. This agent does not issue BUY/SELL.
The Coordinator uses the risk level as a safety overlay.

The risk level is judged on the last 90 trading days, because the
prediction horizon is short. Any longer history (the Data Agent supplies
about a year) is used only as a baseline: if recent volatility is far
above the stock's normal level, that "volatility spike" counts as event
pressure.
"""

from __future__ import annotations

import math

import pandas as pd

from app.agents.base_agent import BaseAgent
from app.guardrails import specialist_output_guardrail
from app.models.schemas import AgentResult

RISK_WINDOW_DAYS = 90
# Need a meaningfully longer history than the risk window for a baseline.
MIN_BASELINE_DAYS = 150
VOL_SPIKE_RATIO = 1.5


class RiskAgent(BaseAgent):
    """Evaluate volatility, drawdown, and short-term swings."""

    name = "risk_agent"

    async def analyze(
        self,
        ticker: str,
        price_history: pd.DataFrame | None = None,
        agent_results: list[AgentResult] | None = None,
    ) -> AgentResult:
        if price_history is None or price_history.empty:
            raise ValueError("RiskAgent requires price_history from the Coordinator.")

        full_close = _close_series(price_history)
        close = full_close.tail(RISK_WINDOW_DAYS).reset_index(drop=True)
        returns = close.pct_change().dropna()
        if returns.empty:
            raise ValueError("Not enough price points to compute risk.")

        annual_vol = _annualized_vol(close)
        baseline_vol = (
            _annualized_vol(full_close) if len(full_close) >= MIN_BASELINE_DAYS else None
        )

        rolling_peak = close.cummax()
        drawdown = (close / rolling_peak) - 1.0
        max_drawdown = float(drawdown.min())

        window = min(5, len(close) - 1)
        five_day_return = float(close.iloc[-1] / close.iloc[-1 - window] - 1.0)
        latest_move = float(returns.iloc[-1])

        event_flags = _event_flags(agent_results)
        if baseline_vol and annual_vol >= VOL_SPIKE_RATIO * baseline_vol:
            event_flags.append(
                f"volatility spike ({annual_vol:.1%} recently vs {baseline_vol:.1%} over the past year)"
            )
        level, reason = _classify_risk(
            annual_vol=annual_vol,
            max_drawdown=max_drawdown,
            five_day_return=five_day_return,
            event_flags=event_flags,
        )
        confidence = _risk_confidence(annual_vol, max_drawdown, len(close))

        baseline_note = (
            f" (1-year baseline {baseline_vol:.1%})" if baseline_vol else ""
        )
        explanation = (
            f"{ticker} risk is {level.upper()}. "
            f"Over the last {len(close)} trading days, annualized volatility is "
            f"{annual_vol:.1%}{baseline_note}, "
            f"max drawdown is {max_drawdown:.1%}, "
            f"and the last {window} sessions returned {five_day_return:.1%} "
            f"(latest daily move {latest_move:.1%}). {reason}"
        )

        result = AgentResult(
            agent_name=self.name,
            signal=level,
            confidence=confidence,
            explanation=explanation,
        )
        return specialist_output_guardrail(result)


def _close_series(price_history: pd.DataFrame) -> pd.Series:
    close_col = next(col for col in price_history.columns if str(col).lower() == "close")
    return price_history[close_col].astype(float)


def _annualized_vol(close: pd.Series) -> float:
    return float(close.pct_change().dropna().std(ddof=1)) * math.sqrt(252)


NEGATIVE_SIGNALS = {"bearish", "sell"}


def _event_flags(agent_results: list[AgentResult] | None) -> list[str]:
    flags: list[str] = []
    for result in agent_results or []:
        if result.agent_name == "sentiment_agent" and result.signal in NEGATIVE_SIGNALS:
            flags.append("bearish news/sentiment")
        if result.agent_name == "fundamental_agent" and result.signal in NEGATIVE_SIGNALS:
            flags.append("weak fundamentals")
    return flags


def _classify_risk(
    annual_vol: float,
    max_drawdown: float,
    five_day_return: float,
    event_flags: list[str],
) -> tuple[str, str]:
    """
    Simple, explainable thresholds (classroom-friendly, not a bank model).

    HIGH: very jumpy prices, deep recent loss, or extra event pressure.
    MEDIUM: elevated vol, a noticeable swing, or event pressure on calm prices.
    LOW: relatively calm recent path with no event pressure.
    """
    deep_loss = max_drawdown <= -0.15 or five_day_return <= -0.08
    jumpy = annual_vol >= 0.40
    elevated = annual_vol >= 0.25 or max_drawdown <= -0.08 or abs(five_day_return) >= 0.05

    if jumpy or deep_loss or (elevated and event_flags):
        extra = ""
        if event_flags:
            extra = " Event pressure: " + ", ".join(event_flags) + "."
        return "high", "This name is too unstable for an aggressive BUY." + extra

    if elevated:
        return "medium", "Swings are large enough that position size should stay conservative."

    if event_flags:
        return "medium", "Prices are calm, but there is event pressure: " + ", ".join(event_flags) + "."

    return "low", "Recent price action is relatively calm."


def _risk_confidence(annual_vol: float, max_drawdown: float, n_days: int) -> float:
    """Higher when the sample is longer and the classification is farther from a threshold."""
    sample = min(1.0, n_days / 90)
    distance = min(abs(annual_vol - 0.25), abs(max_drawdown + 0.08))
    return round(min(0.92, 0.55 + 0.3 * sample + min(0.15, distance)), 4)
