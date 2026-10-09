"""
MarketMind Gradio UI.

Launch from the repo root:
    python -m app.ui

Then open the local URL printed in the terminal (usually
http://127.0.0.1:7860).

One Analyze click runs the Coordinator once and fills the decision
banner, market snapshot, price chart, specialist cards, and guardrail
audit. Chart windows (3M / 6M / 1Y) re-filter without a new analysis.
"""

from __future__ import annotations

import html
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

TICKERS = [SP500_SYMBOL]
HORIZONS = [3, 5, 10]
CHART_WINDOWS = ["3M", "6M", "1Y"]
_WINDOW_TRADING_DAYS = {"3M": 63, "6M": 126, "1Y": 252}

_BG = "#0a1210"
_PANEL = "#101a17"
_GRID = "#1e2e28"
_TEXT = "#e7f0eb"
_MUTED = "#8fa39a"
_ACCENT = "#3dcf9a"
_PRICE = "#5ec8ff"
_SMA20 = "#f0b429"
_SMA50 = "#ff6b4a"

_coordinator = CoordinatorAgent()
_data_agent = DataAgent()

_CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,400&family=Fraunces:opsz,wght@9..144,500;9..144,700&display=swap');

:root {
  --mm-bg: #0a1210;
  --mm-panel: #101a17;
  --mm-line: #1e2e28;
  --mm-text: #e7f0eb;
  --mm-muted: #8fa39a;
  --mm-accent: #3dcf9a;
  --mm-warn: #f0b429;
  --mm-danger: #ff6b4a;
}

.gradio-container {
  font-family: "DM Sans", system-ui, sans-serif !important;
  max-width: 1120px !important;
  margin: 0 auto !important;
  background:
    radial-gradient(1200px 500px at 10% -10%, rgba(61, 207, 154, 0.14), transparent 55%),
    radial-gradient(900px 420px at 95% 0%, rgba(94, 200, 255, 0.10), transparent 50%),
    var(--mm-bg) !important;
  color: var(--mm-text) !important;
}

.mm-hero {
  padding: 1.4rem 0 0.4rem 0;
}
.mm-hero-brand {
  font-family: "Fraunces", Georgia, serif;
  font-size: 2.55rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.05;
  margin: 0;
  color: var(--mm-text);
}
.mm-hero-sub {
  margin: 0.55rem 0 0;
  color: var(--mm-muted);
  font-size: 1.02rem;
  max-width: 42rem;
  line-height: 1.45;
}
.mm-hero-note {
  margin: 0.55rem 0 0;
  color: var(--mm-muted);
  font-size: 0.82rem;
  opacity: 0.85;
}

.mm-decision {
  border: 1px solid var(--mm-line);
  border-radius: 18px;
  padding: 1.15rem 1.35rem;
  background: linear-gradient(145deg, rgba(61,207,154,0.10), rgba(16,26,23,0.95) 45%);
  margin: 0.35rem 0 0.75rem;
}
.mm-decision.buy {
  border-color: rgba(61, 207, 154, 0.45);
  background: linear-gradient(145deg, rgba(61,207,154,0.16), rgba(16,26,23,0.96) 48%);
}
.mm-decision.sell {
  border-color: rgba(255, 107, 74, 0.45);
  background: linear-gradient(145deg, rgba(255,107,74,0.14), rgba(16,26,23,0.96) 48%);
}
.mm-decision.hold {
  border-color: rgba(240, 180, 41, 0.40);
  background: linear-gradient(145deg, rgba(240,180,41,0.12), rgba(16,26,23,0.96) 48%);
}
.mm-decision-kicker {
  color: var(--mm-muted);
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.35rem;
}
.mm-decision-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.75rem;
  align-items: baseline;
}
.mm-decision-rec {
  font-family: "Fraunces", Georgia, serif;
  font-size: 2.2rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1;
}
.mm-decision.buy .mm-decision-rec { color: var(--mm-accent); }
.mm-decision.hold .mm-decision-rec { color: var(--mm-warn); }
.mm-decision.sell .mm-decision-rec { color: var(--mm-danger); }
.mm-decision-meta {
  color: var(--mm-text);
  font-size: 0.98rem;
}
.mm-decision-explain {
  margin-top: 0.75rem;
  color: #c9d8d0;
  font-size: 0.95rem;
  line-height: 1.5;
}

.mm-snap {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.7rem;
  margin: 0.25rem 0 0.9rem;
}
@media (max-width: 820px) {
  .mm-snap { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.mm-snap-card {
  border: 1px solid var(--mm-line);
  border-radius: 14px;
  background: rgba(16, 26, 23, 0.88);
  padding: 0.8rem 0.9rem;
}
.mm-snap-label {
  color: var(--mm-muted);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.mm-snap-value {
  margin-top: 0.25rem;
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--mm-text);
}
.mm-snap-value.up { color: var(--mm-accent); }
.mm-snap-value.down { color: var(--mm-danger); }
.mm-snap-hint {
  margin-top: 0.15rem;
  color: var(--mm-muted);
  font-size: 0.78rem;
}

.mm-agent {
  border: 1px solid var(--mm-line);
  border-radius: 16px;
  background: rgba(16, 26, 23, 0.92);
  padding: 0.95rem 1.05rem;
  height: 100%;
  min-height: 9.5rem;
}
.mm-agent-top {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.55rem;
}
.mm-agent-name {
  font-size: 0.78rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--mm-muted);
}
.mm-agent-signal {
  font-weight: 700;
  font-size: 0.95rem;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  border: 1px solid var(--mm-line);
}
.mm-agent-signal.bullish, .mm-agent-signal.buy, .mm-agent-signal.low {
  color: var(--mm-accent);
  border-color: rgba(61, 207, 154, 0.45);
  background: rgba(61, 207, 154, 0.08);
}
.mm-agent-signal.bearish, .mm-agent-signal.sell, .mm-agent-signal.high {
  color: var(--mm-danger);
  border-color: rgba(255, 107, 74, 0.45);
  background: rgba(255, 107, 74, 0.08);
}
.mm-agent-signal.neutral, .mm-agent-signal.hold, .mm-agent-signal.medium {
  color: var(--mm-warn);
  border-color: rgba(240, 180, 41, 0.4);
  background: rgba(240, 180, 41, 0.08);
}
.mm-agent-signal.unavailable {
  color: var(--mm-muted);
}
.mm-agent-conf {
  color: var(--mm-muted);
  font-size: 0.82rem;
  margin-bottom: 0.45rem;
}
.mm-agent-body {
  color: #c9d8d0;
  font-size: 0.9rem;
  line-height: 1.45;
  white-space: pre-wrap;
}

footer, .svelte-1edxm74 { display: none !important; }
"""


def _signal_class(signal: str) -> str:
    return (signal or "unavailable").strip().lower().replace(" ", "-")


def _format_pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value * 100:+.2f}%"


def _format_number(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:,.{digits}f}"


def _decision_html(final: FinalRecommendation) -> str:
    rec = final.recommendation.upper()
    css = _signal_class(rec)
    explanation = html.escape(final.explanation)
    return f"""
<div class="mm-decision {css}">
  <div class="mm-decision-kicker">Coordinator decision · {html.escape(final.ticker)} · {final.horizon_days} trading days</div>
  <div class="mm-decision-row">
    <div class="mm-decision-rec">{rec}</div>
    <div class="mm-decision-meta">Confidence <strong>{final.confidence:.2f}</strong></div>
  </div>
  <div class="mm-decision-explain">{explanation}</div>
</div>
"""


def _snapshot_html(data: DataAgentResult) -> str:
    if not data.price_history:
        return "<div class='mm-snap'><div class='mm-snap-card'><div class='mm-snap-label'>Market</div><div class='mm-snap-value'>—</div></div></div>"

    closes = [bar.close for bar in data.price_history]
    last = closes[-1]
    prev = closes[-2] if len(closes) > 1 else last
    day_chg = (last / prev - 1.0) if prev else 0.0
    five = closes[-6] if len(closes) > 5 else closes[0]
    five_chg = (last / five - 1.0) if five else 0.0
    window = closes[-63:] if len(closes) >= 63 else closes
    hi = max(window)
    lo = min(window)

    pe = None
    name = html.escape(data.company_info.company_name or data.ticker)
    if data.fundamentals is not None:
        pe = data.fundamentals.trailing_pe

    day_cls = "up" if day_chg >= 0 else "down"
    five_cls = "up" if five_chg >= 0 else "down"

    return f"""
<div class="mm-snap">
  <div class="mm-snap-card">
    <div class="mm-snap-label">Last close · {html.escape(data.ticker)}</div>
    <div class="mm-snap-value">{_format_number(last)}</div>
    <div class="mm-snap-hint">{name}</div>
  </div>
  <div class="mm-snap-card">
    <div class="mm-snap-label">1-day change</div>
    <div class="mm-snap-value {day_cls}">{_format_pct(day_chg)}</div>
    <div class="mm-snap-hint">vs prior close</div>
  </div>
  <div class="mm-snap-card">
    <div class="mm-snap-label">5-day change</div>
    <div class="mm-snap-value {five_cls}">{_format_pct(five_chg)}</div>
    <div class="mm-snap-hint">matches prediction horizon</div>
  </div>
  <div class="mm-snap-card">
    <div class="mm-snap-label">~3M range / P/E</div>
    <div class="mm-snap-value">{_format_number(lo)} – {_format_number(hi)}</div>
    <div class="mm-snap-hint">Trailing P/E {_format_number(pe, 1)}</div>
  </div>
</div>
"""


def _agent_card_html(title: str, result: AgentResult | None) -> str:
    if result is None:
        signal = "unavailable"
        conf = "—"
        body = "This agent returned no result."
    else:
        signal = result.signal.strip().lower()
        conf = "—" if signal == "unavailable" else f"{result.confidence:.2f}"
        body = result.explanation
    css = _signal_class(signal)
    return f"""
<div class="mm-agent">
  <div class="mm-agent-top">
    <div class="mm-agent-name">{html.escape(title)}</div>
    <div class="mm-agent-signal {css}">{html.escape(signal.upper())}</div>
  </div>
  <div class="mm-agent-conf">Confidence {html.escape(str(conf))}</div>
  <div class="mm-agent-body">{html.escape(body)}</div>
</div>
"""


def _guardrail_markdown(final: FinalRecommendation) -> str:
    if not final.guardrails:
        return "_No guardrail events recorded._"
    lines = ["| Kind | Check | Result | Detail |", "| --- | --- | --- | --- |"]
    for event in final.guardrails[:12]:
        mark = "pass" if event.passed else "fail"
        detail = event.detail.replace("|", "/")
        lines.append(f"| {event.kind} | `{event.name}` | **{mark}** | {detail} |")
    if len(final.guardrails) > 12:
        lines.append(f"| … | … | … | +{len(final.guardrails) - 12} more |")
    return "\n".join(lines)


def _empty_chart(message: str = "Run Analyze to load S&P 500 price history."):
    fig, ax = plt.subplots(figsize=(11, 4.6))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.text(
        0.5,
        0.5,
        message,
        ha="center",
        va="center",
        color=_MUTED,
        fontsize=12,
        transform=ax.transAxes,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color(_GRID)
    fig.tight_layout()
    return fig


def build_price_frame(data: DataAgentResult) -> pd.DataFrame:
    """Build chart DataFrame: date, Price, SMA20, SMA50."""
    if not data.price_history:
        return pd.DataFrame(columns=["date", "Price", "SMA20", "SMA50"])

    dates = [bar.date for bar in data.price_history]
    closes = pd.Series([bar.close for bar in data.price_history], dtype=float)
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "Price": closes,
            "SMA20": closes.rolling(window=20, min_periods=20).mean(),
            "SMA50": closes.rolling(window=50, min_periods=50).mean(),
        }
    )


def plot_price_history(
    frame: Optional[pd.DataFrame],
    window: str = "1Y",
) -> plt.Figure:
    """Draw Close + SMA20 + SMA50 for the selected window."""
    if frame is None or frame.empty:
        return _empty_chart()

    days = _WINDOW_TRADING_DAYS.get(window, 252)
    view = frame.tail(days).copy()
    if view.empty:
        return _empty_chart("No price rows in this window.")

    fig, ax = plt.subplots(figsize=(11, 4.6))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_PANEL)

    ax.fill_between(
        view["date"],
        view["Price"],
        view["Price"].min() * 0.995,
        color=_PRICE,
        alpha=0.08,
        linewidth=0,
    )
    ax.plot(view["date"], view["Price"], color=_PRICE, linewidth=1.7, label="Price")
    ax.plot(view["date"], view["SMA20"], color=_SMA20, linewidth=1.35, label="SMA20")
    ax.plot(view["date"], view["SMA50"], color=_SMA50, linewidth=1.35, label="SMA50")

    last = float(view["Price"].iloc[-1])
    ax.annotate(
        f"{last:.2f}",
        xy=(view["date"].iloc[-1], last),
        xytext=(8, 0),
        textcoords="offset points",
        color=_TEXT,
        fontsize=9,
        fontweight="bold",
        va="center",
    )

    ax.set_title(
        f"Price history ({window}) · SMA20 / SMA50",
        color=_TEXT,
        fontsize=12,
        pad=10,
        loc="left",
    )
    ax.set_ylabel("Price", color=_MUTED)
    ax.tick_params(colors=_MUTED, labelsize=8)
    ax.grid(True, color=_GRID, linewidth=0.7, alpha=0.9)
    for spine in ax.spines.values():
        spine.set_color(_GRID)

    legend = ax.legend(
        loc="upper left",
        facecolor=_PANEL,
        edgecolor=_GRID,
        labelcolor=_TEXT,
        fontsize=9,
        framealpha=0.95,
    )
    legend.get_frame().set_linewidth(0.8)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def _idle_decision() -> str:
    return """
<div class="mm-decision hold">
  <div class="mm-decision-kicker">Coordinator decision</div>
  <div class="mm-decision-row">
    <div class="mm-decision-rec">Ready</div>
    <div class="mm-decision-meta">Pick a horizon, then run Analyze</div>
  </div>
  <div class="mm-decision-explain">
    MarketMind will combine Technical, Sentiment, Fundamental, and Risk signals
    into one BUY / HOLD / SELL recommendation for the S&amp;P 500.
  </div>
</div>
"""


def _idle_snapshot() -> str:
    return """
<div class="mm-snap">
  <div class="mm-snap-card">
    <div class="mm-snap-label">Last close</div>
    <div class="mm-snap-value">—</div>
    <div class="mm-snap-hint">Waiting for Analyze</div>
  </div>
  <div class="mm-snap-card">
    <div class="mm-snap-label">1-day change</div>
    <div class="mm-snap-value">—</div>
    <div class="mm-snap-hint">Live from DataAgent</div>
  </div>
  <div class="mm-snap-card">
    <div class="mm-snap-label">5-day change</div>
    <div class="mm-snap-value">—</div>
    <div class="mm-snap-hint">Aligned with horizon</div>
  </div>
  <div class="mm-snap-card">
    <div class="mm-snap-label">Range / P/E</div>
    <div class="mm-snap-value">—</div>
    <div class="mm-snap-hint">After first run</div>
  </div>
</div>
"""


def _idle_agent(title: str) -> str:
    return _agent_card_html(title, None).replace(
        "This agent returned no result.",
        "Run Analyze to populate this specialist.",
    )


async def analyze(ticker: str, horizon_days: int, chart_window: str):
    """Run Coordinator + DataAgent and fill the premium dashboard."""
    try:
        final = await _coordinator.analyze(ticker, horizon_days=horizon_days)
        data = await _data_agent.analyze(ticker)
        frame = build_price_frame(data)
        chart = plot_price_history(frame, chart_window or "1Y")
    except Exception as exc:
        err = (
            f"<div class='mm-decision sell'><div class='mm-decision-kicker'>Error</div>"
            f"<div class='mm-decision-rec'>Failed</div>"
            f"<div class='mm-decision-explain'><strong>{type(exc).__name__}:</strong> {exc}</div></div>"
        )
        empty_agent = _agent_card_html("Agent", None)
        return (
            err,
            _idle_snapshot(),
            _empty_chart(f"Chart unavailable: {type(exc).__name__}"),
            None,
            empty_agent,
            empty_agent,
            empty_agent,
            empty_agent,
            f"**Error:** `{type(exc).__name__}: {exc}`",
        )

    by_agent = {r.agent_name: r for r in final.agent_results}
    return (
        _decision_html(final),
        _snapshot_html(data),
        chart,
        frame,
        _agent_card_html("Technical", by_agent.get("technical_agent")),
        _agent_card_html("Sentiment", by_agent.get("sentiment_agent")),
        _agent_card_html("Fundamental", by_agent.get("fundamental_agent")),
        _agent_card_html("Risk", by_agent.get("risk_agent")),
        _guardrail_markdown(final),
    )


def refresh_chart(frame: Optional[pd.DataFrame], chart_window: str):
    """Re-draw the chart for a new window without re-running agents."""
    return plot_price_history(frame, chart_window or "1Y")


theme = gr.themes.Soft(
    primary_hue="emerald",
    secondary_hue="slate",
    neutral_hue="slate",
    font=gr.themes.GoogleFont("DM Sans"),
).set(
    body_background_fill=_BG,
    body_text_color=_TEXT,
    block_background_fill=_PANEL,
    block_border_color=_GRID,
    block_label_text_color=_MUTED,
    button_primary_background_fill=_ACCENT,
    button_primary_text_color="#04140f",
    border_color_primary=_GRID,
)

with gr.Blocks(title="MarketMind") as demo:
    gr.HTML(
        """
        <div class="mm-hero">
          <h1 class="mm-hero-brand">MarketMind</h1>
          <p class="mm-hero-sub">
            Multi-agent S&amp;P 500 decision support — Technical, Sentiment,
            Fundamental, and Risk signals coordinated into one explainable
            recommendation.
          </p>
          <p class="mm-hero-note">Course demonstration only. Not financial advice.</p>
        </div>
        """
    )

    with gr.Row(equal_height=True):
        ticker_input = gr.Dropdown(
            choices=TICKERS,
            value=SP500_SYMBOL,
            label="Market",
            info="S&P 500 via SPY (Yahoo Finance)",
            scale=2,
        )
        horizon_input = gr.Dropdown(
            choices=HORIZONS,
            value=5,
            label="Horizon (trading days)",
            scale=1,
        )
        analyze_button = gr.Button("Analyze market", variant="primary", scale=1)

    decision_out = gr.HTML(value=_idle_decision())
    snapshot_out = gr.HTML(value=_idle_snapshot())

    with gr.Group():
        price_chart = gr.Plot(value=_empty_chart(), label="Price history")
        chart_window = gr.Radio(
            choices=CHART_WINDOWS,
            value="1Y",
            label="Chart window",
            info="Re-filters instantly — no new agent run",
        )
        price_frame_state = gr.State(None)

    gr.Markdown("### Specialist agents")
    with gr.Row(equal_height=True):
        technical_out = gr.HTML(value=_idle_agent("Technical"))
        sentiment_out = gr.HTML(value=_idle_agent("Sentiment"))
    with gr.Row(equal_height=True):
        fundamental_out = gr.HTML(value=_idle_agent("Fundamental"))
        risk_out = gr.HTML(value=_idle_agent("Risk"))

    with gr.Accordion("Guardrail audit trail", open=False):
        guardrails_out = gr.Markdown("_Run Analyze to see input / tool / output checks._")

    analyze_button.click(
        fn=analyze,
        inputs=[ticker_input, horizon_input, chart_window],
        outputs=[
            decision_out,
            snapshot_out,
            price_chart,
            price_frame_state,
            technical_out,
            sentiment_out,
            fundamental_out,
            risk_out,
            guardrails_out,
        ],
    )

    chart_window.change(
        fn=refresh_chart,
        inputs=[price_frame_state, chart_window],
        outputs=[price_chart],
    )


if __name__ == "__main__":
    demo.launch(theme=theme, css=_CUSTOM_CSS)
