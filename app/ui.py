"""
MarketMind Gradio UI.

Launch from the repo root:
    python -m app.ui

Then open the local URL printed in the terminal (usually
http://127.0.0.1:7860).

The UI is organized as one panel per agent. Each panel consumes the shared
BaseAgent contract (analyze(ticker) -> AgentResult), so teammates can wire
their agents in by replacing the placeholder functions below with calls to
their agents — no UI restructuring needed.
"""

import gradio as gr

from app.agents.fundamental_agent import FundamentalAgent

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]

_fundamental_agent = FundamentalAgent()

_SIGNAL_BADGES = {
    "buy": "🟢 BUY",
    "hold": "🟡 HOLD",
    "sell": "🔴 SELL",
}


async def analyze_fundamentals(ticker: str):
    """Run the Fundamental Analysis agent and format its AgentResult."""
    try:
        result = await _fundamental_agent.analyze(ticker)
    except Exception as exc:  # surface config/API errors in the UI, not a crash
        return "⚠️ Error", "—", f"**{type(exc).__name__}:** {exc}"
    badge = _SIGNAL_BADGES.get(result.signal, result.signal.upper())
    return badge, f"{result.confidence:.2f}", result.explanation


async def placeholder(ticker: str):
    """Stand-in until the owning teammate wires the real agent in."""
    return (
        "—",
        "—",
        "_This agent is not integrated yet. When ready, replace this "
        "placeholder with a call to the agent's `analyze(ticker)` — it "
        "returns the same `AgentResult` shape shown in the Fundamental "
        "panel._",
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
        "decision support. *For course demonstration only — not financial "
        "advice.*"
    )

    with gr.Row():
        ticker_input = gr.Dropdown(
            choices=TICKERS,
            value="AAPL",
            label="Ticker (companies with SEC filings in the vector store)",
        )
        analyze_button = gr.Button("Analyze", variant="primary")

    fundamental_outputs = _agent_panel(
        "Fundamental Analysis", open_by_default=True
    )
    technical_outputs = _agent_panel("Technical Analysis")
    sentiment_outputs = _agent_panel("Sentiment Analysis")
    risk_outputs = _agent_panel("Risk Manager")

    analyze_button.click(
        fn=analyze_fundamentals,
        inputs=ticker_input,
        outputs=list(fundamental_outputs),
    )
    for handler, outputs in [
        (placeholder, technical_outputs),
        (placeholder, sentiment_outputs),
        (placeholder, risk_outputs),
    ]:
        analyze_button.click(
            fn=handler,
            inputs=ticker_input,
            outputs=list(outputs),
        )

    gr.Markdown(
        "_The Coordinator's combined recommendation will appear here once "
        "all specialist agents are integrated._"
    )


if __name__ == "__main__":
    demo.launch()
