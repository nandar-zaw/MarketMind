"""
Coordinator Agent.

Combines the specialist agents' AgentResult outputs into one final
BUY / HOLD / SELL recommendation (FinalRecommendation) using a
deterministic weighted-scoring protocol:

  1. Run the specialist agents in parallel (Fundamental, Technical,
     Sentiment). Agents that fail or are not implemented yet are
     skipped, so the coordinator keeps working as agents come online.
  2. Each result contributes sign(signal) * confidence, weighted by
     the agent's configured weight. Weights renormalize over the
     agents that actually answered.
  3. The weighted score maps to buy/hold/sell with the same ±0.33
     thresholds the specialists use for their own signals.

The decision is arithmetic, not an LLM judgment call: every final
recommendation can be explained line by line (see the explanation
built below). A Risk Manager pass can later veto or downgrade the
proposal before it is returned.
"""

import asyncio

from agents import trace

from app.agents.base_agent import BaseAgent
from app.agents.fundamental_agent import FundamentalAgent
from app.agents.sentiment_agent import SentimentAgent
from app.agents.technical_agent import TechnicalAgent
from app.models.schemas import AgentResult, FinalRecommendation

# Specialist weights (designed to sum to 1.0 when every agent is live).
_WEIGHTS = {
    "fundamental_agent": 0.40,
    "technical_agent": 0.35,
    "sentiment_agent": 0.25,
}

_BUY_THRESHOLD = 0.33
_SELL_THRESHOLD = -0.33

_SIGNAL_SIGN = {"buy": 1.0, "hold": 0.0, "sell": -1.0}


def _signed_score(result: AgentResult) -> float:
    """Map a result to a signed contribution in [-1, 1]."""
    sign = _SIGNAL_SIGN.get(result.signal.strip().lower(), 0.0)
    return sign * max(0.0, min(1.0, result.confidence))


class CoordinatorAgent(BaseAgent):
    """Weighted-scoring coordinator over the specialist agents."""

    name = "coordinator_agent"

    def __init__(self, specialists: list[BaseAgent] | None = None):
        # Injectable so tests can substitute fake specialists without
        # calling the real (LLM-backed) agents.
        self._specialists = (
            specialists
            if specialists is not None
            else [FundamentalAgent(), TechnicalAgent(), SentimentAgent()]
        )

    async def _collect(self, ticker: str) -> list[AgentResult]:
        """Run specialists in parallel; skip any that fail."""
        outcomes = await asyncio.gather(
            *(agent.analyze(ticker) for agent in self._specialists),
            return_exceptions=True,
        )
        return [o for o in outcomes if isinstance(o, AgentResult)]

    async def analyze(self, ticker: str) -> FinalRecommendation:
        ticker = ticker.upper()
        with trace(f"marketmind.coordinator:{ticker}"):
            results = await self._collect(ticker)

        if not results:
            return FinalRecommendation(
                ticker=ticker,
                recommendation="hold",
                confidence=0.0,
                explanation=(
                    "No specialist agent produced a result, so the "
                    "coordinator holds by default."
                ),
                agent_results=[],
            )

        total_weight = sum(
            _WEIGHTS.get(r.agent_name, 0.0) for r in results
        )
        score = 0.0
        lines: list[str] = []
        for r in results:
            weight = _WEIGHTS.get(r.agent_name, 0.0)
            weight_norm = weight / total_weight if total_weight else 0.0
            contribution = weight_norm * _signed_score(r)
            score += contribution
            lines.append(
                f"- {r.agent_name} (weight {weight_norm:.2f}): "
                f"{r.signal.upper()} at {r.confidence:.2f} confidence "
                f"-> contribution {contribution:+.2f}"
            )

        if score >= _BUY_THRESHOLD:
            recommendation = "buy"
        elif score <= _SELL_THRESHOLD:
            recommendation = "sell"
        else:
            recommendation = "hold"

        unavailable = len(self._specialists) - len(results)
        header = f"Weighted score {score:+.2f} from {len(results)} agent(s)"
        if unavailable:
            header += f"; {unavailable} unavailable"
        explanation = header + ".\n" + "\n".join(lines)

        return FinalRecommendation(
            ticker=ticker,
            recommendation=recommendation,
            confidence=round(abs(score), 2),
            explanation=explanation,
            agent_results=results,
        )
