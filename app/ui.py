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
    lines = [
        "",
        "**Guardrail audit trail**",
        "",
        "| Kind | Check | Result | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for event in final.guardrails[:8]:
        detail = event.detail.replace("|", "/")
        result = "pass" if event.passed else "FAIL"
        lines.append(f"| {event.kind} | {event.name} | {result} | {detail} |")
    if len(final.guardrails) > 8:
        lines += ["", f"_and {len(final.guardrails) - 8} more checks_"]
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
    """Company header: name/meta line plus a small price-stats table."""
    if data is None:
        return ""
    info = data.company_info
    lines = [f"### {info.company_name or data.ticker} ({data.ticker})"]
    meta = [part for part in (info.sector, info.industry, info.exchange) if part]
    if info.market_cap:
        meta.append(f"Market cap {_fmt_market_cap(info.market_cap)}")
    if meta:
        lines.append(" · ".join(meta))
    closes = [p.close for p in data.price_history]
    if len(closes) >= 2:
        heads = ["Last close", "1-day change"]
        cells = [f"${closes[-1]:,.2f}", f"{closes[-1] / closes[-2] - 1:+.2%}"]
        if len(closes) >= 6:
            heads.append("5-day change")
            cells.append(f"{closes[-1] / closes[-6] - 1:+.2%}")
        lines += [
            "",
            "| " + " | ".join(heads) + " |",
            "| " + " | ".join("---" for _ in heads) + " |",
            "| " + " | ".join(cells) + " |",
        ]
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
    daily = frame.dropna()
    daily = daily.assign(date=pd.to_datetime(daily["date"]))
    # One point per week (the week's last trading day, real date kept).
    # A year of daily points puts ~250 labels under the axis and they
    # render as an unreadable strip; the indicators above are still
    # computed on the daily series, so the trend is unchanged.
    weekly = daily.groupby(pd.Grouper(key="date", freq="W-FRI")).tail(1)
    return weekly.melt(
        id_vars="date",
        value_vars=["Close", "SMA20", "SMA50"],
        var_name="Series",
        value_name="Price",
    )


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
    window: str = "6M",
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


def _agent_panel(
    title: str,
    open_by_default: bool = False,
    elem_id: str | None = None,
    elem_classes: list[str] | None = None,
):
    with gr.Accordion(title, open=open_by_default, elem_id=elem_id, elem_classes=elem_classes):
        signal = gr.Textbox(
            label="Signal",
            interactive=False,
            elem_id=f"{elem_id}-signal" if elem_id else None,
        )
        confidence = gr.Textbox(label="Confidence (0–1)", interactive=False)
        explanation = gr.Markdown()
    return signal, confidence, explanation


_THEME = gr.themes.Base(
    primary_hue="emerald",
    neutral_hue="slate",
)

# Dark slate look: deep navy panels, green accent, the coordinator
# decision panel reads as the hero of the page. Gradio renders its
# light palette by default, so the semantic variables are pointed at
# the dark end of the same slate ramp the theme already ships.
_CSS = """
:root {
    --background-fill-primary: var(--neutral-950);
    --background-fill-secondary: var(--neutral-900);
    --body-background-fill: var(--background-fill-primary);
    --body-text-color: var(--neutral-100);
    --body-text-color-subdued: var(--neutral-400);
    --block-background-fill: var(--neutral-900);
    --block-border-color: var(--neutral-700);
    --border-color-primary: var(--neutral-700);
    --block-label-text-color: var(--neutral-300);
    --block-label-background-fill: var(--background-fill-secondary);
    --block-label-border-color: var(--border-color-primary);
    --block-title-text-color: var(--neutral-100);
    --panel-background-fill: var(--background-fill-secondary);
    --panel-border-color: var(--border-color-primary);
    --input-background-fill: var(--neutral-900);
    --input-border-color: var(--neutral-600);
    --input-placeholder-color: var(--neutral-500);
    --table-border-color: var(--neutral-700);
    --table-even-background-fill: var(--neutral-950);
    --table-odd-background-fill: var(--neutral-900);
    --table-text-color: var(--body-text-color);
    --code-background-fill: var(--neutral-800);
    --checkbox-label-background-fill: var(--neutral-800);
    --checkbox-label-background-fill-selected: var(--primary-600);
    --checkbox-label-text-color-selected: white;
    --checkbox-background-color-selected: var(--color-accent);
    --checkbox-border-color-selected: var(--color-accent);
}
body { background: var(--neutral-950) !important; }
.gradio-container { max-width: 1180px !important; }
#hero { border: 1px solid #1e5c3a !important; background: linear-gradient(180deg, #0d2317 0%, var(--neutral-900) 92%) !important; }
#hero-signal textarea, #hero-signal input { font-size: 34px !important; font-weight: 800 !important; letter-spacing: .4px; }
.agent-card { border: 1px solid var(--neutral-700) !important; border-radius: 12px !important; }
"""

with gr.Blocks(title="MarketMind", theme=_THEME, css=_CSS) as demo:
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

    final_outputs = _agent_panel(
        "Final Recommendation (Coordinator)", open_by_default=True, elem_id="hero"
    )
    company_output = gr.Markdown()
    chart_output = gr.LinePlot(
        label="Price history with SMA20 and SMA50 (weekly points)",
        x="date",
        y="Price",
        color="Series",
        height=320,
        x_label_angle=-45,
    )
    chart_range = gr.Radio(
        choices=["3M", "6M", "1Y"],
        value="6M",
        label="Chart window (re-filters instantly, no new analysis)",
    )
    chart_state = gr.State(value=None)
    with gr.Row():
        with gr.Column():
            fundamental_outputs = _agent_panel("Fundamental Analysis", open_by_default=True, elem_classes=["agent-card"])
        with gr.Column():
            technical_outputs = _agent_panel("Technical Analysis", open_by_default=True, elem_classes=["agent-card"])
    with gr.Row():
        with gr.Column():
            sentiment_outputs = _agent_panel("Sentiment Analysis", open_by_default=True, elem_classes=["agent-card"])
        with gr.Column():
            risk_outputs = _agent_panel("Risk Manager", open_by_default=True, elem_classes=["agent-card"])

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
        examples=[["AAPL", 5, "6M"], ["TSLA", 5, "6M"], ["NVDA", 10, "3M"]],
        inputs=all_inputs,
        outputs=all_outputs,
        fn=analyze,
        run_on_click=True,
        label="Demo examples (click to run)",
    )


if __name__ == "__main__":
    demo.launch()
