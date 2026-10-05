"""
Classroom guardrails for MarketMind agents.

These follow the same three ideas taught in AI-agent courses:

- Input guardrails: reject bad or unsafe user input before any agent runs.
- Tool guardrails: only allow an approved tool, with safe arguments and
  a valid tool result.
- Output guardrails: force the final answer into the allowed schema
  (BUY/HOLD/SELL, confidence 0-1, required explanation).

If a hard rule is broken, ``GuardrailTripwire`` is raised and the request
is stopped. Soft rules (for example HIGH risk blocking BUY) adjust the
output and are recorded as events the professor can inspect.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from app.models.schemas import (
    AgentResult,
    FinalRecommendation,
    GuardrailEvent,
)

TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}$")
MAX_EXPLANATION_CHARS = 1200
MIN_PRICE_ROWS = 20
ALLOWED_RECOMMENDATIONS = {"BUY", "HOLD", "SELL"}
ALLOWED_SPECIALIST_SIGNALS = {
    "bullish",
    "neutral",
    "bearish",
    "buy",
    "hold",
    "sell",
    "unavailable",
}
ALLOWED_RISK_SIGNALS = {"low", "medium", "high"}
ALLOWED_TOOLS = {
    "get_price_history": {"min_days": 20, "max_days": 252},
}

PROMPT_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "you are now",
    "<script",
    "http://",
    "https://",
)


class GuardrailTripwire(Exception):
    """Raised when a hard guardrail fails and the run must stop."""

    def __init__(self, kind: str, name: str, detail: str):
        self.kind = kind
        self.name = name
        self.detail = detail
        super().__init__(detail)

    def as_event(self) -> GuardrailEvent:
        return GuardrailEvent(
            kind=self.kind,
            name=self.name,
            passed=False,
            detail=self.detail,
        )


def input_guardrail(ticker: str, horizon_days: int = 5) -> tuple[str, list[GuardrailEvent]]:
    """
    Validate the user ticker and prediction horizon.

    Returns the normalized ticker if all hard checks pass.
    """
    events: list[GuardrailEvent] = []
    raw = "" if ticker is None else str(ticker).strip()
    lowered = raw.lower()

    if not raw:
        raise GuardrailTripwire(
            "input",
            "ticker_not_empty",
            "Ticker is required.",
        )

    if any(marker in lowered for marker in PROMPT_INJECTION_MARKERS):
        raise GuardrailTripwire(
            "input",
            "reject_prompt_injection",
            "Input looks like an injection or URL, not a stock ticker.",
        )

    normalized = raw.upper()
    if not TICKER_PATTERN.fullmatch(normalized):
        raise GuardrailTripwire(
            "input",
            "ticker_format",
            "Ticker must be 1-5 letters only (example: AAPL).",
        )

    if not isinstance(horizon_days, int) or horizon_days < 1 or horizon_days > 21:
        raise GuardrailTripwire(
            "input",
            "horizon_range",
            "horizon_days must be an integer between 1 and 21.",
        )

    events.append(
        GuardrailEvent(
            kind="input",
            name="ticker_and_horizon",
            passed=True,
            detail=f"Accepted ticker {normalized} with horizon {horizon_days} days.",
        )
    )
    return normalized, events


def tool_guardrail(tool_name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], GuardrailEvent]:
    """Allow only approved tools and clamp their arguments to safe ranges."""
    spec = ALLOWED_TOOLS.get(tool_name)
    if spec is None:
        raise GuardrailTripwire(
            "tool",
            "tool_allowlist",
            f"Tool '{tool_name}' is not on the allowlist.",
        )

    days = int(arguments.get("days", 90))
    if days < spec["min_days"] or days > spec["max_days"]:
        raise GuardrailTripwire(
            "tool",
            "lookback_limit",
            f"get_price_history days must be between {spec['min_days']} and {spec['max_days']}.",
        )

    ticker = arguments.get("ticker", "")
    if not TICKER_PATTERN.fullmatch(str(ticker).upper()):
        raise GuardrailTripwire(
            "tool",
            "tool_ticker",
            "Tool calls must use a validated 1-5 letter ticker.",
        )

    safe_args = {"ticker": str(ticker).upper(), "days": days}
    event = GuardrailEvent(
        kind="tool",
        name="allowlist_and_limits",
        passed=True,
        detail=f"Allowed {tool_name}({safe_args['ticker']}, days={days}).",
    )
    return safe_args, event


def tool_output_guardrail(prices: pd.DataFrame) -> GuardrailEvent:
    """Reject empty or malformed price history from the market-data tool."""
    if prices is None or not isinstance(prices, pd.DataFrame) or prices.empty:
        raise GuardrailTripwire(
            "tool",
            "price_history_schema",
            "Market data tool returned no price rows.",
        )

    columns = {str(col).lower() for col in prices.columns}
    if "close" not in columns:
        raise GuardrailTripwire(
            "tool",
            "price_history_schema",
            "Market data tool result must include a Close column.",
        )

    if len(prices) < MIN_PRICE_ROWS:
        raise GuardrailTripwire(
            "tool",
            "price_history_length",
            f"Need at least {MIN_PRICE_ROWS} trading days of prices.",
        )

    return GuardrailEvent(
        kind="tool",
        name="price_history_schema",
        passed=True,
        detail=f"Price history accepted ({len(prices)} rows).",
    )


def specialist_output_guardrail(result: AgentResult) -> AgentResult:
    """Keep a specialized-agent result inside the shared schema."""
    signal = (result.signal or "").strip().lower()
    if result.agent_name == "risk_agent":
        allowed = ALLOWED_RISK_SIGNALS
    else:
        allowed = ALLOWED_SPECIALIST_SIGNALS

    if signal not in allowed:
        raise GuardrailTripwire(
            "output",
            "agent_signal_vocab",
            f"{result.agent_name} produced invalid signal '{result.signal}'.",
        )

    confidence = _clip_confidence(result.confidence)
    explanation = (result.explanation or "").strip()
    if not explanation:
        raise GuardrailTripwire(
            "output",
            "agent_explanation_required",
            f"{result.agent_name} must include an explanation.",
        )

    return result.model_copy(
        update={
            "signal": signal,
            "confidence": confidence,
            "explanation": explanation[:MAX_EXPLANATION_CHARS],
        }
    )


def decision_output_guardrail(
    recommendation: FinalRecommendation,
    risk_signal: str | None,
) -> tuple[FinalRecommendation, list[GuardrailEvent]]:
    """
    Enforce the final decision contract.

    Hard rules: allowed recommendation labels, confidence bounds, explanation.
    Soft rule: HIGH risk cannot result in BUY (capital-preservation policy).
    """
    events: list[GuardrailEvent] = []
    rec = (recommendation.recommendation or "").strip().upper()
    if rec not in ALLOWED_RECOMMENDATIONS:
        raise GuardrailTripwire(
            "output",
            "recommendation_vocab",
            f"Final recommendation must be BUY, HOLD, or SELL, not '{recommendation.recommendation}'.",
        )

    explanation = (recommendation.explanation or "").strip()
    if not explanation:
        raise GuardrailTripwire(
            "output",
            "final_explanation_required",
            "Final recommendation must include an explanation.",
        )

    confidence = _clip_confidence(recommendation.confidence)
    events.append(
        GuardrailEvent(
            kind="output",
            name="schema_contract",
            passed=True,
            detail="Recommendation, confidence, and explanation are valid.",
        )
    )

    if risk_signal == "high" and rec == "BUY":
        rec = "HOLD"
        confidence = min(confidence, 0.45)
        explanation = (
            "Output guardrail: HIGH risk blocked BUY and downgraded the "
            "decision to HOLD. "
            + explanation
        )
        events.append(
            GuardrailEvent(
                kind="output",
                name="high_risk_blocks_buy",
                passed=True,
                detail="Soft policy applied: BUY was rewritten to HOLD.",
            )
        )
    else:
        events.append(
            GuardrailEvent(
                kind="output",
                name="high_risk_blocks_buy",
                passed=True,
                detail="No BUY+HIGH-risk rewrite needed.",
            )
        )

    guarded = recommendation.model_copy(
        update={
            "recommendation": rec,
            "confidence": confidence,
            "explanation": explanation[:MAX_EXPLANATION_CHARS],
            "guardrails": list(recommendation.guardrails) + events,
        }
    )
    return guarded, events


def _clip_confidence(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise GuardrailTripwire(
            "output",
            "confidence_numeric",
            "Confidence must be a number between 0 and 1.",
        ) from exc

    if number < 0 or number > 1:
        raise GuardrailTripwire(
            "output",
            "confidence_bounds",
            "Confidence must be between 0 and 1.",
        )
    return round(number, 4)
