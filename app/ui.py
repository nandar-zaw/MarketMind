"""
MarketMind Gradio UI.

Launch from the repo root:
    python -m app.ui

Then open the local URL printed in the terminal (usually
http://127.0.0.1:7860).

One Analyze click runs the Coordinator once; it calls the specialist
agents (Fundamental, Technical, Sentiment) plus the Risk Manager and
returns a FinalRecommendation. Every panel below renders from that one
result: the agent panels read FinalRecommendation.agent_results, and
the final panel shows the recommendation with its guardrail audit
trail. Teammates never need to touch this file: when a specialist
starts returning real results instead of "unavailable", its panel
fills in automatically.
"""

import gradio as gr

from app.agents.coordinator_agent import CoordinatorAgent
from app.models.schemas import AgentResult, FinalRecommendation
from app.utils.symbols import SP500_SYMBOL

# MarketMind currently focuses on the S&P 500 (SPY ETF proxy via yfinance).
TICKERS = [SP500_SYMBOL]
HORIZONS = [3, 5, 10]

_coordinator = CoordinatorAgent()

_SIGNAL_BADGES = {
    "buy": "🟢 BUY",
    "bullish": "🟢 BULLISH",
    "hold": "🟡 HOLD",
    "neutral": "🟡 NEUTRAL",
    "sell": "🔴 SELL",
    "bearish": "🔴 BEARISH",
    "unavailable": "⚪ UNAVAILABLE",
    "low": "🟢 LOW",
    "medium": "🟡 MEDIUM",
    "high": "🔴 HIGH",
}


def _badge(signal: str) -> str:
    return _SIGNAL_BADGES.get(signal.strip().lower(), signal.upper())


def _panel_values(result: AgentResult | None):
    """Format one agent panel (signal, confidence, explanation)."""
    if result is None:
        return "—", "—", "_This agent returned no result._"
    if result.signal.strip().lower() == "unavailable":
        return _badge(result.signal), "—", result.explanation
    return _badge(result.signal), f"{result.confidence:.2f}", result.explanation


def _guardrail_lines(final: FinalRecommendation) -> str:
    """Render the guardrail audit trail stored on the final result."""
    if not final.guardrails:
        return ""
    lines = ["", "**Guardrail checks**"]
    for event in final.guardrails[:8]:
        mark = "✅" if event.passed else "⛔"
        lines.append(f"- {mark} {event.kind} {event.name}: {event.detail}")
    if len(final.guardrails) > 8:
        lines.append(f"- … and {len(final.guardrails) - 8} more")
    return "\n".join(lines)


async def analyze(ticker: str, horizon_days: int):
    """Run the Coordinator once and fill every panel from its result."""
    try:
        final = await _coordinator.analyze(ticker, horizon_days=horizon_days)
    except Exception as exc:  # surface config/API/data errors, not a crash
        error = ("—", "—", f"⚠️ **{type(exc).__name__}:** {exc}")
        return (*error, *error, *error, *error, *error)
    by_agent = {r.agent_name: r for r in final.agent_results}
    final_values = (
        _badge(final.recommendation),
        f"{final.confidence:.2f}",
        f"{final.explanation}\n\n_Horizon: {final.horizon_days} trading days._"
        + _guardrail_lines(final),
    )
    return (
        *final_values,
        *_panel_values(by_agent.get("fundamental_agent")),
        *_panel_values(by_agent.get("technical_agent")),
        *_panel_values(by_agent.get("sentiment_agent")),
        *_panel_values(by_agent.get("risk_agent")),
    )


def _agent_panel(title: str, open_by_default: bool = False):
    with gr.Accordion(title, open=open_by_default):
        signal = gr.Textbox(label="Signal", interactive=False)
        confidence = gr.Textbox(label="Confidence (0–1)", interactive=False)
        explanation = gr.Markdown()
    return signal, confidence, explanation


with gr.Blocks(title="MarketMind") as demo:
    gr.Markdown(
        "# MarketMind\n"
        "Multi-agent system for S&P 500 trend prediction and investment "
        "decision support. *For course demonstration only. Not financial "
        "advice.*"
    )

    with gr.Row():
        ticker_input = gr.Dropdown(
            choices=TICKERS,
            value=SP500_SYMBOL,
            label="Market (S&P 500 via SPY ETF proxy on Yahoo Finance)",
        )
        horizon_input = gr.Dropdown(
            choices=HORIZONS,
            value=5,
            label="Horizon (trading days)",
        )
        analyze_button = gr.Button("Analyze", variant="primary")

    final_outputs = _agent_panel(
        "Final Recommendation (Coordinator)", open_by_default=True
    )
    fundamental_outputs = _agent_panel("Fundamental Analysis")
    technical_outputs = _agent_panel("Technical Analysis")
    sentiment_outputs = _agent_panel("Sentiment Analysis")
    risk_outputs = _agent_panel("Risk Manager")

    analyze_button.click(
        fn=analyze,
        inputs=[ticker_input, horizon_input],
        outputs=[
            *final_outputs,
            *fundamental_outputs,
            *technical_outputs,
            *sentiment_outputs,
            *risk_outputs,
        ],
    )


if __name__ == "__main__":
    demo.launch()
