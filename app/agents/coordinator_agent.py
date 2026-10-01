"""
Coordinator Agent placeholder.

Future responsibility:
Collect outputs from all specialized agents and create the final
BUY / HOLD / SELL recommendation with confidence, explanation,
and supporting signals.
"""

from app.agents.base_agent import BaseAgent


class CoordinatorAgent(BaseAgent):
    """
    Future responsibility:
    Combine all agent signals into one final recommendation.
    """

    name = "coordinator_agent"

    async def analyze(self, ticker: str):
        # TODO: In Phase 6, call other agents and merge their results.
        # Do NOT invent fake BUY/HOLD/SELL recommendations in Phase 1.
        raise NotImplementedError(
            "Coordinator logic will be implemented in Phase 6."
        )
