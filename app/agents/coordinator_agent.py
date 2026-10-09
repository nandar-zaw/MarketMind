"""
Coordinator / Decision Agent.

Job: gather specialist signals, ask Risk Manager to review them, then
produce one BUY / HOLD / SELL recommendation for the next 5 trading days.

Market data is loaded once through the Data Collector Agent, then shared
with Technical, Sentiment, and Risk. Fundamental uses its own SEC-filing
RAG source (not DataAgent).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, timedelta

import pandas as pd

from app.agents.base_agent import BaseAgent
from app.agents.data_agent import DataAgent
from app.agents.fundamental_agent import FundamentalAgent
from app.agents.risk_agent import RiskAgent
from app.agents.sentiment_agent import SentimentAgent
from app.agents.technical_agent import TechnicalAgent
from app.guardrails import (
    GuardrailTripwire,
    decision_output_guardrail,
    input_guardrail,
    specialist_output_guardrail,
    tool_guardrail,
    tool_output_guardrail,
)
from app.models.schemas import (
    AgentResult,
    CompanyInfo,
    DataAgentResult,
    FinalRecommendation,
    GuardrailEvent,
    MarketPrice,
)
from app.utils.exceptions import MarketDataError

SIGNAL_SCORE = {
    "bullish": 1.0,
    "neutral": 0.0,
    "bearish": -1.0,
    "buy": 1.0,
    "hold": 0.0,
    "sell": -1.0,
    "unavailable": 0.0,
}
SPECIALIST_WEIGHTS = {
    "technical_agent": 0.35,
    "sentiment_agent": 0.20,
    "fundamental_agent": 0.20,
}
INTERIM_RETURN_WEIGHT = 0.25

# Agents that consume DataAgentResult directly (prices / news / fundamentals).
_DATA_CONSUMERS = {"technical_agent", "sentiment_agent", "fundamental_agent"}


class CoordinatorAgent(BaseAgent):
    """Combine agent evidence into one guarded decision."""

    name = "coordinator_agent"

    def __init__(
        self,
        data_agent: DataAgent | None = None,
        risk_agent: RiskAgent | None = None,
        specialists: dict[str, BaseAgent] | None = None,
        price_fetcher: Callable[..., Awaitable[pd.DataFrame] | pd.DataFrame] | None = None,
    ):
        self.data_agent = data_agent or DataAgent()
        self.risk_agent = risk_agent or RiskAgent()
        self.specialists = specialists or {
            "technical_agent": TechnicalAgent(data_agent=self.data_agent),
            "sentiment_agent": SentimentAgent(data_agent=self.data_agent),
            "fundamental_agent": FundamentalAgent(data_agent=self.data_agent),
        }
        # Optional test hook: inject a DataFrame instead of calling DataAgent.
        self.price_fetcher = price_fetcher

    async def analyze(self, ticker: str, horizon_days: int = 5) -> FinalRecommendation:
        guardrails: list[GuardrailEvent] = []
        ticker, input_events = input_guardrail(ticker, horizon_days)
        guardrails.extend(input_events)

        data, prices = await self._load_market_data(ticker, guardrails)
        specialist_results = await self._collect_specialists(ticker, data)
        risk_result = await self.risk_agent.analyze(
            ticker,
            price_history=prices,
            agent_results=specialist_results,
        )
        risk_result = specialist_output_guardrail(risk_result)

        close = _close_series(prices)
        steps = min(horizon_days, len(close) - 1)
        horizon_return = (
            float(close.iloc[-1] / close.iloc[-1 - steps] - 1.0) if steps else 0.0
        )

        recommendation, confidence, explanation = _decide(
            specialist_results=specialist_results,
            risk_result=risk_result,
            horizon_return=horizon_return,
            horizon_days=horizon_days,
            ticker=ticker,
        )

        draft = FinalRecommendation(
            ticker=ticker,
            recommendation=recommendation,
            confidence=confidence,
            explanation=explanation,
            horizon_days=horizon_days,
            agent_results=[*specialist_results, risk_result],
            guardrails=guardrails,
        )
        final, _ = decision_output_guardrail(draft, risk_signal=risk_result.signal)
        return final

    async def _load_market_data(
        self,
        ticker: str,
        guardrails: list[GuardrailEvent],
    ) -> tuple[DataAgentResult, pd.DataFrame]:
        """
        Load market data once for all agents that need it.

        Normal path: DataAgent (OHLCV + company info + news).
        Test path: optional price_fetcher returns a price DataFrame only.
        """
        safe_args, tool_event = tool_guardrail(
            "get_price_history",
            {"ticker": ticker, "days": 90},
        )
        guardrails.append(tool_event)

        try:
            if self.price_fetcher is not None:
                prices = self.price_fetcher(**safe_args)
                if hasattr(prices, "__await__"):
                    prices = await prices  # type: ignore[misc]
                data = _dataframe_to_data_result(safe_args["ticker"], prices)
            else:
                data = await self.data_agent.analyze(safe_args["ticker"])
                prices = _market_prices_to_dataframe(data.price_history)
                prices = prices.tail(safe_args["days"])
        except MarketDataError as exc:
            raise GuardrailTripwire("tool", "market_data_failure", str(exc)) from exc

        guardrails.append(tool_output_guardrail(prices))
        return data, prices

    async def _collect_specialists(
        self,
        ticker: str,
        data: DataAgentResult,
    ) -> list[AgentResult]:
        results: list[AgentResult] = []
        for name, agent in self.specialists.items():
            try:
                if name in _DATA_CONSUMERS:
                    try:
                        raw = await agent.analyze(ticker, data=data)
                    except TypeError:
                        # Stub agents in tests may not accept ``data=``.
                        raw = await agent.analyze(ticker)
                else:
                    raw = await agent.analyze(ticker)
                results.append(specialist_output_guardrail(raw))
            except (NotImplementedError, Exception) as exc:
                results.append(
                    specialist_output_guardrail(
                        AgentResult(
                            agent_name=name,
                            signal="unavailable",
                            confidence=0.0,
                            explanation=(
                                f"{name} is unavailable ({type(exc).__name__}: {exc}), "
                                "so it does not vote. Coordinator uses risk + "
                                "short-horizon price context instead."
                            ),
                        )
                    )
                )
        return results


def _market_prices_to_dataframe(price_history: list[MarketPrice]) -> pd.DataFrame:
    """Convert DataAgent OHLCV bars into the DataFrame RiskAgent expects."""
    if not price_history:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    return pd.DataFrame(
        {
            "Open": [bar.open for bar in price_history],
            "High": [bar.high for bar in price_history],
            "Low": [bar.low for bar in price_history],
            "Close": [bar.close for bar in price_history],
            "Volume": [bar.volume for bar in price_history],
        }
    )


def _dataframe_to_data_result(ticker: str, frame: pd.DataFrame) -> DataAgentResult:
    """Build a DataAgentResult from a test-injected price DataFrame."""
    prices: list[MarketPrice] = []
    n = len(frame)
    today = date.today()
    for i, row in enumerate(frame.itertuples()):
        prices.append(
            MarketPrice(
                date=today - timedelta(days=n - i),
                open=float(row.Open),
                high=float(row.High),
                low=float(row.Low),
                close=float(row.Close),
                volume=int(getattr(row, "Volume", 0) or 0),
            )
        )
    return DataAgentResult(
        ticker=ticker,
        company_info=CompanyInfo(ticker=ticker),
        price_history=prices,
        news=[],
        start_date=prices[0].date if prices else None,
        end_date=prices[-1].date if prices else None,
        records_count=len(prices),
    )


def _close_series(price_history: pd.DataFrame) -> pd.Series:
    close_col = next(col for col in price_history.columns if str(col).lower() == "close")
    return price_history[close_col].astype(float)


def _decide(
    specialist_results: list[AgentResult],
    risk_result: AgentResult,
    horizon_return: float,
    horizon_days: int,
    ticker: str,
) -> tuple[str, float, str]:
    score = 0.0
    weight_sum = 0.0
    live_specialists: list[str] = []

    for result in specialist_results:
        if result.signal == "unavailable":
            continue
        weight = SPECIALIST_WEIGHTS.get(result.agent_name, 0.1)
        score += weight * SIGNAL_SCORE.get(result.signal, 0.0) * max(result.confidence, 0.2)
        weight_sum += weight
        live_specialists.append(f"{result.agent_name}={result.signal}")

    # Interim context only while technical analysis is still a teammate TODO.
    technical_live = any(
        r.agent_name == "technical_agent" and r.signal != "unavailable"
        for r in specialist_results
    )
    if not technical_live:
        return_signal = _return_to_signal(horizon_return)
        score += INTERIM_RETURN_WEIGHT * SIGNAL_SCORE[return_signal]
        weight_sum += INTERIM_RETURN_WEIGHT
        live_specialists.append(f"interim_{horizon_days}d_return={return_signal}")

    blended = 0.0 if weight_sum == 0 else score / weight_sum
    if blended > 0.25:
        recommendation = "BUY"
    elif blended < -0.25:
        recommendation = "SELL"
    else:
        recommendation = "HOLD"

    if risk_result.signal == "high" and recommendation == "BUY":
        recommendation = "HOLD"
    if risk_result.signal == "high" and blended <= -0.15:
        recommendation = "SELL"
    if risk_result.signal == "medium" and recommendation == "BUY":
        # Medium risk can still buy, but confidence is later capped.
        pass

    agreement = min(1.0, abs(blended))
    confidence = round(
        min(0.9, 0.4 + 0.35 * agreement + 0.15 * risk_result.confidence),
        4,
    )
    if risk_result.signal == "high":
        confidence = min(confidence, 0.5)
    elif risk_result.signal == "medium":
        confidence = min(confidence, 0.7)

    evidence = ", ".join(live_specialists) if live_specialists else "no live specialist votes"
    explanation = (
        f"{ticker} recommendation is {recommendation} for the next {horizon_days} trading days. "
        f"Blended evidence score is {blended:+.2f} ({evidence}). "
        f"Risk Manager says {risk_result.signal.upper()} risk. "
        f"{horizon_days}-day return is {horizon_return:.1%}."
    )
    return recommendation, confidence, explanation


def _return_to_signal(horizon_return: float) -> str:
    if horizon_return >= 0.03:
        return "bullish"
    if horizon_return <= -0.03:
        return "bearish"
    return "neutral"
