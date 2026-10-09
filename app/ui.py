"""
MarketMind Gradio UI.

Launch from the repo root:
    python -m app.ui

Then open the local URL printed in the terminal (usually
http://127.0.0.1:7860).

One Analyze click runs the Coordinator once; it calls the specialist
agents (Fundamental, Technical, Sentiment) plus the Risk Manager and
returns a FinalRecommendation. Every panel below renders from that one
result. A price-history chart (Close + SMA20/SMA50) is built from the
same DataAgent pull and can be re-filtered to 3M / 6M / 1Y without
running analysis again.
"""

from __future__ import annotations

from typing import Optional

import gradio as gr
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.data_agent import DataAgent
from app.models.schemas import AgentResult, DataAgentResult, FinalRecommendation
from app.utils.symbols import SP500_SYMBOL

# MarketMind currently focuses on the S&P 500 (SPY ETF proxy via yfinance).
TICKERS = [SP500_SYMBOL]
HORIZONS = [3, 5, 10]
CHART_WINDOWS = ["3M", "6M", "1Y"]
_WINDOW_TRADING_DAYS = {"3M": 63, "6M": 126, "1Y": 252}

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


def _empty_chart(message: str = "Click Analyze to load price history."):
    """Placeholder figure before the first successful analyze."""
    fig, ax = plt.subplots(figsize=(10, 4.2))
    fig.patch.set_facecolor("#0b0f14")
    ax.set_facecolor("#0b0f14")
    ax.text(
        0.5,
        0.5,
        message,
        ha="center",
        va="center",
        color="#9aa4b2",
        fontsize=12,
        transform=ax.transAxes,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#2a3340")
    fig.tight_layout()
    return fig


def build_price_frame(data: DataAgentResult) -> pd.DataFrame:
    """
    Build a chart DataFrame from DataAgent OHLCV bars.

    Columns: date, Price, SMA20, SMA50 (oldest → newest).
    """
    if not data.price_history:
        return pd.DataFrame(columns=["date", "Price", "SMA20", "SMA50"])

    dates = [bar.date for bar in data.price_history]
    closes = pd.Series([bar.close for bar in data.price_history], dtype=float)
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "Price": closes,
            "SMA20": closes.rolling(window=20, min_periods=20).mean(),
            "SMA50": closes.rolling(window=50, min_periods=50).mean(),
        }
    )
    return frame


def plot_price_history(
    frame: Optional[pd.DataFrame],
    window: str = "1Y",
) -> plt.Figure:
    """
    Draw Close + SMA20 + SMA50 for the selected window.

    Re-filtering the window does not call the Coordinator again.
    """
    if frame is None or frame.empty:
        return _empty_chart()

    days = _WINDOW_TRADING_DAYS.get(window, 252)
    view = frame.tail(days).copy()
    if view.empty:
        return _empty_chart("No price rows in this window.")

    fig, ax = plt.subplots(figsize=(10, 4.2))
    fig.patch.set_facecolor("#0b0f14")
    ax.set_facecolor("#0b0f14")

    ax.plot(view["date"], view["Price"], color="#4C9BE8", linewidth=1.4, label="Price")
    ax.plot(view["date"], view["SMA20"], color="#F0A202", linewidth=1.3, label="SMA20")
    ax.plot(view["date"], view["SMA50"], color="#E4572E", linewidth=1.3, label="SMA50")

    ax.set_title(
        f"Price history ({window}) with SMA20 and SMA50",
        color="#e8eef7",
        fontsize=12,
        pad=10,
    )
    ax.set_ylabel("Price", color="#c5ced9")
    ax.set_xlabel("date", color="#c5ced9")
    ax.tick_params(colors="#9aa4b2", labelsize=8)
    ax.grid(True, color="#2a3340", linewidth=0.6)
    for spine in ax.spines.values():
        spine.set_color("#2a3340")

    legend = ax.legend(
        loc="upper left",
        facecolor="#121821",
        edgecolor="#2a3340",
        labelcolor="#e8eef7",
        fontsize=9,
    )
    legend.get_frame().set_alpha(0.95)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def _panel_error(message: str):
    return ("—", "—", message)


async def analyze(ticker: str, horizon_days: int, chart_window: str):
    """Run the Coordinator once and fill every panel + price chart."""
    try:
        final = await _coordinator.analyze(ticker, horizon_days=horizon_days)
        # Same market pull the specialists use — used here for the chart.
        data = await _data_agent.analyze(ticker)
        frame = build_price_frame(data)
        chart = plot_price_history(frame, chart_window or "1Y")
    except Exception as exc:  # surface config/API/data errors, not a crash
        error = _panel_error(f"⚠️ **{type(exc).__name__}:** {exc}")
        empty = _empty_chart(f"Chart unavailable: {type(exc).__name__}")
        return (*error, *error, *error, *error, *error, empty, None)

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
        chart,
        frame,
    )


def refresh_chart(frame: Optional[pd.DataFrame], chart_window: str):
    """Re-draw the chart for a new window without re-running agents."""
    return plot_price_history(frame, chart_window or "1Y")


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

    with gr.Accordion("Price history", open=True):
        price_chart = gr.Plot(value=_empty_chart(), label="Price history")
        chart_window = gr.Radio(
            choices=CHART_WINDOWS,
            value="1Y",
            label="Chart window (re-filters instantly, no new analysis)",
        )
        price_frame_state = gr.State(None)

    final_outputs = _agent_panel(
        "Final Recommendation (Coordinator)", open_by_default=True
    )
    fundamental_outputs = _agent_panel("Fundamental Analysis")
    technical_outputs = _agent_panel("Technical Analysis")
    sentiment_outputs = _agent_panel("Sentiment Analysis")
    risk_outputs = _agent_panel("Risk Manager")

    analyze_button.click(
        fn=analyze,
        inputs=[ticker_input, horizon_input, chart_window],
        outputs=[
            *final_outputs,
            *fundamental_outputs,
            *technical_outputs,
            *sentiment_outputs,
            *risk_outputs,
            price_chart,
            price_frame_state,
        ],
    )

    chart_window.change(
        fn=refresh_chart,
        inputs=[price_frame_state, chart_window],
        outputs=[price_chart],
    )


if __name__ == "__main__":
    demo.launch()
