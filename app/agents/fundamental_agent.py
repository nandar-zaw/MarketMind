"""
Fundamental Analysis Agent.

Analyzes company fundamentals (revenue growth, margins, valuation,
balance sheet health, risk factors) using RAG over SEC filings
(10-K / 10-Q) via OpenAI's FileSearchTool.

Implements the BaseAgent interface: analyze(ticker) -> AgentResult.
The Coordinator calls this the same way it calls every other agent.

Setup:
  1. Upload the filings to a vector store at platform.openai.com
     (Dashboard -> Storage -> Vector Stores -> "marketmind-fundamentals").
  2. Set FUNDAMENTALS_VECTOR_STORE_ID=vs_... in your .env
"""

import os
import re

from dotenv import load_dotenv

from agents import Agent, Runner, trace, FileSearchTool

from app.agents.base_agent import BaseAgent
from app.models.schemas import AgentResult

load_dotenv(override=True)

_INSTRUCTIONS = (
    "You are a fundamental equity analyst. You answer ONLY from the company "
    "filings retrieved with the file search tool (10-K annual reports and 10-Q "
    "quarterly reports). Never use general knowledge or guess numbers.\n\n"
    "For the given ticker, assess:\n"
    "1. Revenue growth (latest year / quarter vs prior periods)\n"
    "2. Profitability: gross margin and operating margin trends\n"
    "3. Valuation: P/E or P/S relative to the company's own history if disclosed\n"
    "4. Balance sheet health: cash position, total debt, debt-to-equity\n"
    "5. Key risks stated in the filing's Risk Factors section\n\n"
    "Return your answer in EXACTLY this format:\n"
    "SCORE: <number from -1.0 (strong sell) to +1.0 (strong buy)>\n"
    "EVIDENCE:\n"
    "- <bullet with a concrete number and the filing it came from>\n"
    "- <bullet with a concrete number and the filing it came from>\n"
    "- <bullet with a concrete number and the filing it came from>\n"
    "VERDICT: <one sentence>\n\n"
    "If a data point is not in the retrieved filings, write 'not disclosed in "
    "retrieved filings' instead of inventing it."
)

# Score thresholds for the buy/hold/sell signal (tunable).
_BUY_THRESHOLD = 0.33
_SELL_THRESHOLD = -0.33


def _build_agent() -> Agent:
    """Build the underlying SDK agent. Fails fast with a clear message if the
    vector store is not configured."""
    vector_store_id = os.environ.get("FUNDAMENTALS_VECTOR_STORE_ID")
    if not vector_store_id:
        raise RuntimeError(
            "FUNDAMENTALS_VECTOR_STORE_ID is not set. Upload the filings to a "
            "vector store (platform.openai.com -> Storage -> Vector Stores) "
            "and add FUNDAMENTALS_VECTOR_STORE_ID=vs_... to your .env file."
        )
    return Agent(
        name="Fundamental Analyst",
        instructions=_INSTRUCTIONS,
        tools=[FileSearchTool(vector_store_ids=[vector_store_id])],
    )


def _parse_output(text: str) -> tuple[float, list[str], str]:
    """Parse the agent's structured text into (score, evidence, verdict)."""
    score_match = re.search(r"^SCORE:\s*([-+]?\d*\.?\d+)", text, re.MULTILINE)
    score = float(score_match.group(1)) if score_match else 0.0
    score = max(-1.0, min(1.0, score))  # clamp to [-1, 1]

    verdict_match = re.search(r"^VERDICT:\s*(.+)$", text, re.MULTILINE)
    verdict = verdict_match.group(1).strip() if verdict_match else ""

    evidence: list[str] = []
    in_evidence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("EVIDENCE:"):
            in_evidence = True
            continue
        if stripped.startswith("VERDICT:"):
            break
        if in_evidence and stripped.startswith("- "):
            evidence.append(stripped[2:].strip())
    return score, evidence, verdict


def _signal_for(score: float) -> str:
    if score >= _BUY_THRESHOLD:
        return "buy"
    if score <= _SELL_THRESHOLD:
        return "sell"
    return "hold"


class FundamentalAgent(BaseAgent):
    """Fundamental analysis via RAG over SEC filings."""

    name = "fundamental_agent"

    async def analyze(self, ticker: str) -> AgentResult:
        agent = _build_agent()
        with trace(f"marketmind.fundamental_agent:{ticker}"):
            result = await Runner.run(agent, f"Analyze the fundamentals of {ticker}.")

        score, evidence, verdict = _parse_output(result.final_output)
        explanation = verdict
        if evidence:
            explanation += "\n" + "\n".join(f"- {bullet}" for bullet in evidence)

        return AgentResult(
            agent_name=self.name,
            signal=_signal_for(score),
            confidence=round(abs(score), 2),
            explanation=explanation,
        )
