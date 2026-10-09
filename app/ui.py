"""
MarketMind Gradio UI.

Launch from the repo root:
    python -m app.ui

Then open the local URL printed in the terminal (usually
http://127.0.0.1:7860).

One Analyze click runs the Coordinator once and fills the decision
banner, market snapshot, price chart, specialist cards, and a quick
summary / recommendation. Chart windows re-filter without a new analysis.
"""

from __future__ import annotations

import html
import os
from typing import Optional

import gradio as gr
import matplotlib
from dotenv import load_dotenv

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.data_agent import DataAgent
from app.models.schemas import AgentResult, DataAgentResult, FinalRecommendation
from app.utils.symbols import SP500_SYMBOL

load_dotenv(override=True)

TICKERS = [SP500_SYMBOL]
HORIZONS = [3, 5, 10]
# 1D = intraday (5-minute bars); other windows use daily closes.
CHART_WINDOWS = ["1D", "5D", "1M", "3M", "6M", "1Y"]
_WINDOW_TRADING_DAYS = {
    "5D": 5,
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
}

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

.mm-summary {
  border: 1px solid var(--mm-line);
  border-radius: 18px;
  background: linear-gradient(160deg, rgba(16, 26, 23, 0.98), rgba(10, 18, 16, 0.96));
  padding: 1.15rem 1.3rem 1.25rem;
  margin: 0.35rem 0 0.5rem;
}
.mm-summary-kicker {
  color: var(--mm-muted);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.45rem;
}
.mm-summary-title {
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--mm-text);
  margin: 0 0 0.65rem;
  line-height: 1.25;
}
.mm-summary-title.buy { color: var(--mm-accent); }
.mm-summary-title.hold { color: var(--mm-warn); }
.mm-summary-title.sell { color: var(--mm-danger); }
.mm-summary-lead {
  color: #c9d8d0;
  font-size: 0.95rem;
  line-height: 1.5;
  margin: 0 0 0.9rem;
}
.mm-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
  margin-bottom: 0.85rem;
}
@media (max-width: 820px) {
  .mm-summary-grid { grid-template-columns: 1fr; }
}
.mm-summary-chip {
  border: 1px solid var(--mm-line);
  border-radius: 12px;
  background: rgba(10, 18, 16, 0.65);
  padding: 0.65rem 0.75rem;
}
.mm-summary-chip-label {
  color: var(--mm-muted);
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.mm-summary-chip-value {
  margin-top: 0.2rem;
  color: var(--mm-text);
  font-size: 0.92rem;
  font-weight: 600;
  line-height: 1.35;
}
.mm-summary-bullets {
  margin: 0;
  padding-left: 1.1rem;
  color: #c9d8d0;
  font-size: 0.9rem;
  line-height: 1.5;
}
.mm-summary-bullets li {
  margin: 0.2rem 0;
}
.mm-summary-note {
  margin: 0.75rem 0 0;
  color: var(--mm-muted);
  font-size: 0.78rem;
  line-height: 1.4;
}

/* Hide Gradio's default footer; we render our own API footer. */
footer.svelte-app-footer,
.gradio-container > footer {
  display: none !important;
}

.mm-api-footer {
  margin: 1.6rem 0 0.4rem;
  padding: 1.05rem 1.15rem 1.2rem;
  border: 1px solid var(--mm-line);
  border-radius: 16px;
  background: rgba(12, 20, 17, 0.92);
}
.mm-api-footer h3 {
  margin: 0 0 0.65rem;
  font-family: "Fraunces", Georgia, serif;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--mm-text);
}
.mm-api-footer table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.mm-api-footer th,
.mm-api-footer td {
  text-align: left;
  padding: 0.45rem 0.55rem;
  border-top: 1px solid var(--mm-line);
  vertical-align: top;
  color: #c9d8d0;
}
.mm-api-footer th {
  color: var(--mm-muted);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-top: none;
}
.mm-api-footer .mm-api-name {
  color: var(--mm-accent);
  font-weight: 700;
  white-space: nowrap;
}
.mm-api-footer .mm-api-note {
  margin: 0.75rem 0 0;
  color: var(--mm-muted);
  font-size: 0.78rem;
  line-height: 1.4;
}

/* Premium horizontal control toolbar */
.mm-toolbar {
  border: 1px solid var(--mm-line) !important;
  border-radius: 18px !important;
  background: linear-gradient(180deg, rgba(22, 34, 30, 0.95), rgba(12, 20, 17, 0.98)) !important;
  padding: 0.95rem 1.05rem 1.05rem !important;
  margin: 0.35rem 0 1rem !important;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.22);
}
.mm-toolbar-caption {
  margin: 0 0 0.75rem;
  color: var(--mm-muted);
  font-size: 0.82rem;
  letter-spacing: 0.02em;
}
.mm-toolbar-row {
  display: flex !important;
  flex-direction: row !important;
  align-items: flex-end !important;
  gap: 0.85rem !important;
  flex-wrap: wrap !important;
}
.mm-field {
  display: flex !important;
  flex-direction: column !important;
  gap: 0.35rem !important;
  min-width: 0 !important;
}
.mm-field-action {
  display: flex !important;
  flex-direction: column !important;
  justify-content: flex-end !important;
  min-width: 160px !important;
}
.mm-label {
  display: block;
  margin: 0;
  padding: 0;
  color: var(--mm-muted);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: transparent !important;
  border: none !important;
}
.mm-label-spacer {
  visibility: hidden;
  height: 0.95rem;
}
.mm-toolbar .mm-analyze-btn,
.mm-toolbar button {
  min-height: 44px !important;
  height: 44px !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
  letter-spacing: 0.01em !important;
  box-shadow: 0 6px 18px rgba(61, 207, 154, 0.22);
}
.mm-toolbar .wrap,
.mm-toolbar .container,
.mm-toolbar .form,
.mm-toolbar .block {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
}
.mm-toolbar input,
.mm-toolbar .secondary-wrap,
.mm-toolbar [data-testid="dropdown"],
.mm-toolbar .svelte-select-wrap {
  border-radius: 12px !important;
}
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


def _agent_by_name(
    results: list[AgentResult], name: str
) -> AgentResult | None:
    for result in results:
        if result.agent_name == name:
            return result
    return None


def _signal_phrase(signal: str | None) -> str:
    if not signal or signal == "unavailable":
        return "no vote"
    return signal.strip().lower()


def _recommendation_headline(rec: str) -> str:
    mapping = {
        "BUY": "Lean into strength — bias toward BUY",
        "HOLD": "Stay patient — bias toward HOLD",
        "SELL": "Protect capital — bias toward SELL",
    }
    return mapping.get(rec.upper(), f"Recommendation: {rec.upper()}")


def _recommendation_action(rec: str, horizon_days: int, risk: str) -> str:
    rec = rec.upper()
    risk = (risk or "medium").lower()
    if rec == "BUY":
        base = (
            f"For the next ~{horizon_days} trading days, evidence favors adding "
            "or keeping exposure if it fits your plan."
        )
    elif rec == "SELL":
        base = (
            f"For the next ~{horizon_days} trading days, evidence favors reducing "
            "exposure or waiting for a cleaner setup."
        )
    else:
        base = (
            f"For the next ~{horizon_days} trading days, evidence is mixed — "
            "prefer waiting over forcing a trade."
        )
    if risk == "high":
        return base + " Risk is HIGH, so keep position size conservative."
    if risk == "low":
        return base + " Risk looks relatively contained."
    return base + " Risk is moderate — size positions carefully."


def _summary_html(final: FinalRecommendation) -> str:
    """Footer panel: plain-language takeaway instead of a guardrail audit table."""
    rec = (final.recommendation or "HOLD").upper()
    css = _signal_class(rec)
    tech = _agent_by_name(final.agent_results, "technical_agent")
    sent = _agent_by_name(final.agent_results, "sentiment_agent")
    fund = _agent_by_name(final.agent_results, "fundamental_agent")
    risk = _agent_by_name(final.agent_results, "risk_agent")
    risk_signal = _signal_phrase(risk.signal if risk else None)
    if risk_signal == "no vote":
        risk_signal = "unknown"

    votes = []
    for label, agent in (
        ("Technical", tech),
        ("Sentiment", sent),
        ("Fundamental", fund),
    ):
        votes.append(f"{label}: {_signal_phrase(agent.signal if agent else None)}")

    bullets: list[str] = []
    if tech and tech.signal != "unavailable":
        bullets.append(f"Technical leans {tech.signal} (confidence {tech.confidence:.2f}).")
    elif tech:
        bullets.append("Technical did not vote (unavailable).")

    if sent and sent.signal != "unavailable":
        bullets.append(f"News sentiment leans {sent.signal} (confidence {sent.confidence:.2f}).")
    elif sent:
        bullets.append("Sentiment did not vote (too little news or unavailable).")

    if fund and fund.signal != "unavailable":
        bullets.append(
            f"Fundamentals lean {fund.signal} (confidence {fund.confidence:.2f})."
        )
    elif fund:
        bullets.append("Fundamentals did not vote (metrics unavailable).")

    if risk and risk.signal != "unavailable":
        bullets.append(f"Risk overlay is {risk.signal.upper()}.")

    action = _recommendation_action(rec, final.horizon_days, risk_signal)
    bullet_html = "".join(f"<li>{html.escape(item)}</li>" for item in bullets)
    vote_line = " · ".join(votes)

    return f"""
<div class="mm-summary">
  <div class="mm-summary-kicker">Quick summary · {html.escape(final.ticker)} · {final.horizon_days} trading days</div>
  <h2 class="mm-summary-title {css}">{html.escape(_recommendation_headline(rec))}</h2>
  <p class="mm-summary-lead">{html.escape(action)}</p>
  <div class="mm-summary-grid">
    <div class="mm-summary-chip">
      <div class="mm-summary-chip-label">Decision</div>
      <div class="mm-summary-chip-value">{html.escape(rec)} · conf {final.confidence:.2f}</div>
    </div>
    <div class="mm-summary-chip">
      <div class="mm-summary-chip-label">Specialist votes</div>
      <div class="mm-summary-chip-value">{html.escape(vote_line)}</div>
    </div>
    <div class="mm-summary-chip">
      <div class="mm-summary-chip-label">Risk</div>
      <div class="mm-summary-chip-value">{html.escape(risk_signal.upper())}</div>
    </div>
  </div>
  <ul class="mm-summary-bullets">{bullet_html}</ul>
  <p class="mm-summary-note">Course demonstration only. Not financial advice.</p>
</div>
"""


def _idle_summary() -> str:
    return """
<div class="mm-summary">
  <div class="mm-summary-kicker">Quick summary</div>
  <h2 class="mm-summary-title hold">Run Analyze for a recommendation</h2>
  <p class="mm-summary-lead">
    After one run you will see a plain-language takeaway, how the specialists voted,
    and what the risk overlay implies for the next few trading days.
  </p>
  <div class="mm-summary-grid">
    <div class="mm-summary-chip">
      <div class="mm-summary-chip-label">Decision</div>
      <div class="mm-summary-chip-value">—</div>
    </div>
    <div class="mm-summary-chip">
      <div class="mm-summary-chip-label">Specialist votes</div>
      <div class="mm-summary-chip-value">Waiting for Analyze</div>
    </div>
    <div class="mm-summary-chip">
      <div class="mm-summary-chip-label">Risk</div>
      <div class="mm-summary-chip-value">—</div>
    </div>
  </div>
  <p class="mm-summary-note">Course demonstration only. Not financial advice.</p>
</div>
"""


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
    """Build daily chart DataFrame: date, Price, SMA20, SMA50."""
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


def build_intraday_frame(raw: Optional[pd.DataFrame]) -> pd.DataFrame:
    """
    Build a 1D chart DataFrame from yfinance intraday bars.

    Uses shorter moving averages suited to 5-minute data (SMA20 / SMA50
    of 5m bars ≈ last ~1.5–4 trading hours).
    """
    if raw is None or raw.empty or "Close" not in raw.columns:
        return pd.DataFrame(columns=["date", "Price", "SMA20", "SMA50"])

    closes = raw["Close"].astype(float)
    return pd.DataFrame(
        {
            "date": pd.to_datetime(raw.index),
            "Price": closes.to_numpy(),
            "SMA20": closes.rolling(window=20, min_periods=5).mean().to_numpy(),
            "SMA50": closes.rolling(window=50, min_periods=10).mean().to_numpy(),
        }
    ).reset_index(drop=True)


def _resolve_chart_view(
    chart_data: Optional[dict | pd.DataFrame],
    window: str,
) -> tuple[pd.DataFrame, str]:
    """
    Pick the series for the selected window.

    Returns (view_frame, title_suffix).
    Supports legacy plain DataFrames (daily-only) for tests.
    """
    window = (window or "1Y").upper()

    if isinstance(chart_data, pd.DataFrame) or chart_data is None:
        daily = chart_data if isinstance(chart_data, pd.DataFrame) else pd.DataFrame()
        intraday = pd.DataFrame()
    else:
        daily = chart_data.get("daily")
        intraday = chart_data.get("intraday")
        if daily is None:
            daily = pd.DataFrame()
        if intraday is None:
            intraday = pd.DataFrame()

    if window == "1D":
        if intraday is None or intraday.empty:
            return pd.DataFrame(), "1D · no intraday data"
        return intraday.copy(), "1D · 5-minute bars"

    if daily is None or daily.empty:
        return pd.DataFrame(), f"{window} · no daily data"

    days = _WINDOW_TRADING_DAYS.get(window, 252)
    view = daily.tail(days).copy()
    label = {
        "5D": "5D · daily closes",
        "1M": "1M · daily closes",
        "3M": "3M · daily closes",
        "6M": "6M · daily closes",
        "1Y": "1Y · daily closes",
    }.get(window, f"{window} · daily closes")
    return view, label


def plot_price_history(
    chart_data: Optional[dict | pd.DataFrame] = None,
    window: str = "1Y",
    frame: Optional[pd.DataFrame] = None,
) -> plt.Figure:
    """
    Draw Close + SMA overlays for the selected window.

    ``chart_data`` is normally ``{"daily": df, "intraday": df}``.
    The older ``frame=`` kwarg (daily-only) still works for tests.
    """
    if frame is not None and chart_data is None:
        chart_data = frame

    window_key = (window or "1Y").upper()
    view, title = _resolve_chart_view(chart_data, window_key)
    if view.empty:
        return _empty_chart(
            "No price rows in this window."
            if "no " not in title.lower()
            else f"Chart unavailable ({title})."
        )

    fig, ax = plt.subplots(figsize=(11, 4.6))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_PANEL)

    y_floor = float(view["Price"].min()) * 0.995
    ax.fill_between(
        view["date"],
        view["Price"],
        y_floor,
        color=_PRICE,
        alpha=0.08,
        linewidth=0,
    )
    ax.plot(view["date"], view["Price"], color=_PRICE, linewidth=1.7, label="Price")
    if view["SMA20"].notna().any():
        ax.plot(
            view["date"],
            view["SMA20"],
            color=_SMA20,
            linewidth=1.35,
            label="SMA20",
        )
    if view["SMA50"].notna().any():
        ax.plot(
            view["date"],
            view["SMA50"],
            color=_SMA50,
            linewidth=1.35,
            label="SMA50",
        )

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
        f"Price history · {title}",
        color=_TEXT,
        fontsize=12,
        pad=10,
        loc="left",
    )
    ax.set_ylabel("Price", color=_MUTED)
    ax.set_xlabel("time" if window_key == "1D" else "date", color=_MUTED)
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
        daily_frame = build_price_frame(data)
        try:
            intraday_raw = _data_agent.market_data.get_intraday_ohlcv(ticker)
            intraday_frame = build_intraday_frame(intraday_raw)
        except Exception:
            # Daily chart still works if intraday is unavailable (weekends, etc.).
            intraday_frame = pd.DataFrame(
                columns=["date", "Price", "SMA20", "SMA50"]
            )
        chart_bundle = {"daily": daily_frame, "intraday": intraday_frame}
        chart = plot_price_history(chart_bundle, chart_window or "1Y")
    except Exception as exc:
        err = (
            f"<div class='mm-decision sell'><div class='mm-decision-kicker'>Error</div>"
            f"<div class='mm-decision-rec'>Failed</div>"
            f"<div class='mm-decision-explain'><strong>{type(exc).__name__}:</strong> {exc}</div></div>"
        )
        empty_agent = _agent_card_html("Agent", None)
        err_summary = f"""
<div class="mm-summary">
  <div class="mm-summary-kicker">Quick summary</div>
  <h2 class="mm-summary-title sell">Analysis did not finish</h2>
  <p class="mm-summary-lead"><strong>{html.escape(type(exc).__name__)}:</strong> {html.escape(str(exc))}</p>
  <p class="mm-summary-note">Fix the error above, then run Analyze again.</p>
</div>
"""
        return (
            err,
            _idle_snapshot(),
            _empty_chart(f"Chart unavailable: {type(exc).__name__}"),
            None,
            empty_agent,
            empty_agent,
            empty_agent,
            empty_agent,
            err_summary,
        )

    by_agent = {r.agent_name: r for r in final.agent_results}
    return (
        _decision_html(final),
        _snapshot_html(data),
        chart,
        chart_bundle,
        _agent_card_html("Technical", by_agent.get("technical_agent")),
        _agent_card_html("Sentiment", by_agent.get("sentiment_agent")),
        _agent_card_html("Fundamental", by_agent.get("fundamental_agent")),
        _agent_card_html("Risk", by_agent.get("risk_agent")),
        _summary_html(final),
    )


def refresh_chart(chart_data: Optional[dict | pd.DataFrame], chart_window: str):
    """Re-draw the chart for a new window without re-running agents."""
    return plot_price_history(chart_data, chart_window or "1Y")


def _api_footer_html() -> str:
    """Footer explaining which external APIs power each MarketMind feature."""
    openai_ready = bool(os.getenv("OPENAI_API_KEY"))
    openai_status = (
        "Configured — Sentiment can use LLM scoring"
        if openai_ready
        else "Not set — Sentiment uses keyword fallback on headlines"
    )
    return f"""
<div class="mm-api-footer">
  <h3>APIs &amp; data sources</h3>
  <table>
    <thead>
      <tr>
        <th>API / library</th>
        <th>Used for</th>
        <th>Used by</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="mm-api-name">Yahoo Finance via yfinance</td>
        <td>Daily &amp; intraday OHLCV prices, fund metadata, fundamental metrics, news headlines, 1D chart bars</td>
        <td>DataAgent → Technical, Sentiment, Fundamental, Risk, price chart</td>
      </tr>
      <tr>
        <td class="mm-api-name">OpenAI API</td>
        <td>Optional LLM sentiment scoring when <code>OPENAI_API_KEY</code> is set</td>
        <td>Sentiment Agent · <em>{html.escape(openai_status)}</em></td>
      </tr>
      <tr>
        <td class="mm-api-name">FastAPI</td>
        <td>HTTP API (<code>/health</code>, <code>/analyze/{{ticker}}</code>)</td>
        <td><code>app/main.py</code> · run with <code>uvicorn app.main:app</code></td>
      </tr>
      <tr>
        <td class="mm-api-name">Gradio</td>
        <td>This interactive dashboard UI</td>
        <td><code>python -m app.ui</code></td>
      </tr>
    </tbody>
  </table>
  <p class="mm-api-note">
    MarketMind focuses on <strong>SPY</strong> (S&amp;P 500 ETF proxy).
    No SEC file-storage / vector-store API is required for the default path.
    Course demonstration only — not financial advice.
  </p>
</div>
"""


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
    block_label_background_fill="transparent",
    block_label_border_width="0px",
    block_title_text_color=_MUTED,
    button_primary_background_fill=_ACCENT,
    button_primary_text_color="#04140f",
    border_color_primary=_GRID,
    input_background_fill="#0f1815",
    input_border_color=_GRID,
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

    with gr.Group(elem_classes=["mm-toolbar"]):
        gr.HTML(
            '<p class="mm-toolbar-caption">'
            "Analyze the S&amp;P 500 via <strong>SPY</strong> · Yahoo Finance data · "
            "multi-agent recommendation"
            "</p>"
        )
        with gr.Row(elem_classes=["mm-toolbar-row"]):
            with gr.Column(scale=3, min_width=180, elem_classes=["mm-field"]):
                gr.HTML('<span class="mm-label">Market</span>')
                ticker_input = gr.Dropdown(
                    choices=TICKERS,
                    value=SP500_SYMBOL,
                    show_label=False,
                    container=False,
                )
            with gr.Column(scale=2, min_width=150, elem_classes=["mm-field"]):
                gr.HTML('<span class="mm-label">Horizon (trading days)</span>')
                horizon_input = gr.Dropdown(
                    choices=HORIZONS,
                    value=5,
                    show_label=False,
                    container=False,
                )
            with gr.Column(scale=2, min_width=170, elem_classes=["mm-field-action"]):
                gr.HTML('<span class="mm-label mm-label-spacer">Action</span>')
                analyze_button = gr.Button(
                    "Analyze market",
                    variant="primary",
                    elem_classes=["mm-analyze-btn"],
                )

    decision_out = gr.HTML(value=_idle_decision())
    snapshot_out = gr.HTML(value=_idle_snapshot())

    with gr.Group():
        price_chart = gr.Plot(value=_empty_chart(), label="Price history")
        chart_window = gr.Radio(
            choices=CHART_WINDOWS,
            value="1Y",
            label="Chart window",
            info="1D = intraday 5m bars · others = daily closes (no new agent run)",
        )
        price_frame_state = gr.State(None)

    gr.Markdown("### Specialist agents")
    with gr.Row(equal_height=True):
        technical_out = gr.HTML(value=_idle_agent("Technical"))
        sentiment_out = gr.HTML(value=_idle_agent("Sentiment"))
    with gr.Row(equal_height=True):
        fundamental_out = gr.HTML(value=_idle_agent("Fundamental"))
        risk_out = gr.HTML(value=_idle_agent("Risk"))

    summary_out = gr.HTML(value=_idle_summary())

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
            summary_out,
        ],
    )

    chart_window.change(
        fn=refresh_chart,
        inputs=[price_frame_state, chart_window],
        outputs=[price_chart],
    )

    gr.HTML(value=_api_footer_html())


if __name__ == "__main__":
    demo.launch(theme=theme, css=_CUSTOM_CSS)
