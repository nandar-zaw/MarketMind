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

The company header and the price chart come from the DataAgent (the
same data layer the specialists use) and are best-effort: if that
fetch fails, the recommendation panels still render.

On page load the dashboard runs one analysis for the default
ticker, so it opens populated instead of blank. While a run is in
flight the UI reports staged progress, and the chart window
(3M / 6M / 1Y) re-filters the already-loaded prices instantly,
without new data or model calls.
"""

import gradio as gr
import pandas as pd

from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.data_agent import DataAgent
from app.models.schemas import AgentResult, DataAgentResult, FinalRecommendation

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]
HORIZONS = [3, 5, 10]

_coordinator = CoordinatorAgent()
_data_agent = DataAgent()

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


def _fmt_market_cap(value: float) -> str:
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if value >= 1e6:
        return f"${value / 1e6:.0f}M"
    return f"${value:,.0f}"


def _company_markdown(data: DataAgentResult | None) -> str:
    """One-line company header (name, sector, industry, market cap)."""
    if data is None:
        return ""
    info = data.company_info
    lines = [f"### {info.company_name or data.ticker} ({data.ticker})"]
    meta = [part for part in (info.sector, info.industry, info.exchange) if part]
    if info.market_cap:
        meta.append(f"Market cap {_fmt_market_cap(info.market_cap)}")
    if meta:
        lines.append(" · ".join(meta))
    return "\n".join(lines)


def _chart_frame(data: DataAgentResult | None):
    """Long-format price frame (Close, SMA20, SMA50) for gr.LinePlot."""
    if data is None or len(data.price_history) < 2:
        return None
    frame = pd.DataFrame(
        {
            "date": [p.date for p in data.price_history],
            "Close": [p.close for p in data.price_history],
        }
    )
    frame["SMA20"] = frame["Close"].rolling(window=20).mean()
    frame["SMA50"] = frame["Close"].rolling(window=50).mean()
    return frame.melt(
        id_vars="date",
        value_vars=["Close", "SMA20", "SMA50"],
        var_name="Series",
        value_name="Price",
    ).dropna()


def _filter_chart(frame, window: str):
    """Slice a full 1-year chart frame to a 3M / 6M window.

    Pure re-filter of data the page already holds (kept in gr.State),
    so changing the window costs no fetch and no model call.
    """
    if frame is None or len(frame) == 0 or window == "1Y":
        return frame
    months = {"3M": 3, "6M": 6}.get(window)
    if months is None:
        return frame
    dates = pd.to_datetime(frame["date"])
    cutoff = dates.max() - pd.DateOffset(months=months)
    return frame[dates >= cutoff]


async def _visual_data(ticker: str) -> DataAgentResult | None:
    """Best-effort DataAgent pull behind the chart/company header."""
    try:
        return await _data_agent.analyze(ticker)
    except Exception:
        return None


async def analyze(
    ticker: str,
    horizon_days: int,
    window: str = "1Y",
    progress=gr.Progress(),
):
    """Run the Coordinator once and fill every panel from its result."""
    progress(0.1, desc="Running the agent pipeline (specialists + risk review)…")
    try:
        final = await _coordinator.analyze(ticker, horizon_days=horizon_days)
    except Exception as exc:  # surface config/API/data errors, not a crash
        error = ("—", "—", f"⚠️ **{type(exc).__name__}:** {exc}")
        return (*error, *error, *error, *error, *error, None, "", None)
    by_agent = {r.agent_name: r for r in final.agent_results}
    final_values = (
        _badge(final.recommendation),
        f"{final.confidence:.2f}",
        f"{final.explanation}\n\n_Horizon: {final.horizon_days} trading days._"
        + _guardrail_lines(final),
    )
    progress(0.8, desc="Building price chart and company header…")
    data = await _visual_data(final.ticker)
    frame = _chart_frame(data)
    return (
        *final_values,
        *_panel_values(by_agent.get("fundamental_agent")),
        *_panel_values(by_agent.get("technical_agent")),
        *_panel_values(by_agent.get("sentiment_agent")),
        *_panel_values(by_agent.get("risk_agent")),
        _filter_chart(frame, window),
        _company_markdown(data),
        frame,
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
        "advice.*\n\n"
        "**How it works:** the Coordinator asks the DataAgent for prices, "
        "company info, and news → Technical, Sentiment, and Fundamental "
        "agents vote → the Risk Manager reviews → final BUY / HOLD / SELL "
        "with a guardrail audit trail."
    )

    with gr.Row():
        ticker_input = gr.Dropdown(
            choices=TICKERS,
            value="AAPL",
            allow_custom_value=True,
            label="Ticker (type any symbol; the 5 listed have SEC filings in the vector store)",
        )
        horizon_input = gr.Dropdown(
            choices=HORIZONS,
            value=5,
            label="Horizon (trading days)",
        )
        analyze_button = gr.Button("Analyze", variant="primary")

    company_output = gr.Markdown()

    final_outputs = _agent_panel(
        "Final Recommendation (Coordinator)", open_by_default=True
    )
    chart_output = gr.LinePlot(
        label="Price history (1 year) with SMA20 and SMA50",
        x="date",
        y="Price",
        color="Series",
        height=320,
    )
    chart_range = gr.Radio(
        choices=["3M", "6M", "1Y"],
        value="1Y",
        label="Chart window (re-filters instantly, no new analysis)",
    )
    chart_state = gr.State(value=None)
    fundamental_outputs = _agent_panel("Fundamental Analysis")
    technical_outputs = _agent_panel("Technical Analysis")
    sentiment_outputs = _agent_panel("Sentiment Analysis")
    risk_outputs = _agent_panel("Risk Manager")

    all_outputs = [
        *final_outputs,
        *fundamental_outputs,
        *technical_outputs,
        *sentiment_outputs,
        *risk_outputs,
        chart_output,
        company_output,
        chart_state,
    ]
    all_inputs = [ticker_input, horizon_input, chart_range]

    analyze_button.click(
        fn=analyze,
        inputs=all_inputs,
        outputs=all_outputs,
    )
    # Open populated, not blank: run the default analysis on load.
    demo.load(
        fn=analyze,
        inputs=all_inputs,
        outputs=all_outputs,
    )
    chart_range.change(
        fn=_filter_chart,
        inputs=[chart_state, chart_range],
        outputs=chart_output,
    )
    gr.Examples(
        examples=[["AAPL", 5, "1Y"], ["TSLA", 5, "6M"], ["NVDA", 10, "3M"]],
        inputs=all_inputs,
        outputs=all_outputs,
        fn=analyze,
        run_on_click=True,
        label="Demo examples (click to run)",
    )


if __name__ == "__main__":
    demo.launch()
