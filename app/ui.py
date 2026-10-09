"""
MarketMind Gradio UI.

Launch from the repo root:
    python -m app.ui

Then open the local URL printed in the terminal (usually
http://127.0.0.1:7860).

The layout is a single-screen "market terminal":

* top bar with live session status and data-source chips
* quote header (price, change, sparkline) next to the run controls
* interactive Plotly price chart with segmented window control,
  beside the coordinator verdict and the agent pipeline
* KPI tiles, analyst brief, headlines, and specialist reports
* API / data-source footer with the full disclaimer

One Analyze click runs the Coordinator once. Chart windows re-filter
the cached data without a new analysis. Guardrails still run on every
request, but their audit trail stays internal.
"""

from __future__ import annotations

import asyncio
import html
import os
from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

import gradio as gr
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv

from app.agents.coordinator_agent import CoordinatorAgent
from app.agents.data_agent import DataAgent
from app.models.schemas import AgentResult, DataAgentResult, FinalRecommendation
from app.utils.symbols import SP500_SYMBOL

load_dotenv(override=True)

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

_BG = "#080b11"
_PANEL = "#0f141c"
_LINE = "#1d2532"
_TEXT = "#e7ecf3"
_MUTED = "#8691a3"
_UP = "#2fd38a"
_DOWN = "#ff5d5d"
_WARN = "#f5b544"
_BRAND = "#7c8cff"
_SMA20 = "#f5b544"
_SMA50 = "#b38cff"

_NY = ZoneInfo("America/New_York")

_SPECIALISTS = (
    ("technical_agent", "Technical", "RSI · SMA · MACD · volume"),
    ("sentiment_agent", "Sentiment", "News headline tone"),
    ("fundamental_agent", "Fundamental", "Valuation & quality metrics"),
    ("risk_agent", "Risk", "Volatility · drawdown overlay"),
)

_coordinator = CoordinatorAgent()
_data_agent = DataAgent()

_CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
  --mm-bg: #080b11;
  --mm-panel: #0f141c;
  --mm-panel-2: #131a24;
  --mm-line: #1d2532;
  --mm-line-2: #283244;
  --mm-text: #e7ecf3;
  --mm-sub: #b4bdcb;
  --mm-muted: #8691a3;
  --mm-up: #2fd38a;
  --mm-down: #ff5d5d;
  --mm-warn: #f5b544;
  --mm-brand: #7c8cff;
  --mm-brand-2: #4fd1ff;
  --mm-radius: 14px;
  --mm-mono: "JetBrains Mono", ui-monospace, monospace;
}

body, gradio-app { background: var(--mm-bg) !important; }
.gradio-container {
  font-family: "Inter", system-ui, -apple-system, sans-serif !important;
  max-width: 1360px !important;
  margin: 0 auto !important;
  padding: 0 1.25rem 2rem !important;
  color: var(--mm-text) !important;
  background:
    radial-gradient(900px 420px at 0% -10%, rgba(124, 140, 255, 0.10), transparent 60%),
    radial-gradient(800px 380px at 100% -8%, rgba(79, 209, 255, 0.07), transparent 55%),
    var(--mm-bg) !important;
}
.gradio-container .main, .gradio-container .wrap, .gradio-container .contain { gap: 0 !important; }
footer, .gradio-container > footer { display: none !important; }
.gradio-container .column, .gradio-container .row { gap: 1rem !important; }
.mm-num { font-family: var(--mm-mono); font-variant-numeric: tabular-nums; }

/* ---------- Top bar ---------- */
.mm-topbar {
  position: sticky; top: 0; z-index: 50;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  flex-wrap: wrap;
  margin: 0 -1.25rem 1.1rem; padding: 0.8rem 1.25rem;
  border-bottom: 1px solid var(--mm-line);
  background: rgba(8, 11, 17, 0.82);
  backdrop-filter: blur(16px) saturate(140%);
}
.mm-brand { display: flex; align-items: center; gap: 0.7rem; }
.mm-logo {
  width: 34px; height: 34px; border-radius: 10px;
  display: grid; place-items: center;
  background: linear-gradient(135deg, var(--mm-brand), var(--mm-brand-2));
  box-shadow: 0 6px 18px rgba(124, 140, 255, 0.35);
}
.mm-brand-name { font-size: 1.05rem; font-weight: 800; letter-spacing: -0.02em; color: var(--mm-text); }
.mm-brand-tag {
  margin-left: 0.15rem; padding: 0.12rem 0.45rem; border-radius: 6px;
  border: 1px solid var(--mm-line-2); color: var(--mm-muted);
  font-size: 0.66rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
}
.mm-status { display: flex; flex-wrap: wrap; gap: 0.45rem; align-items: center; }
.mm-chip {
  display: inline-flex; align-items: center; gap: 0.42rem;
  padding: 0.3rem 0.65rem; border-radius: 999px;
  border: 1px solid var(--mm-line); background: rgba(15, 20, 28, 0.9);
  color: var(--mm-muted); font-size: 0.74rem; font-weight: 500; white-space: nowrap;
}
.mm-chip b { color: var(--mm-text); font-weight: 600; }
.mm-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--mm-muted); }
.mm-dot.up { background: var(--mm-up); box-shadow: 0 0 0 3px rgba(47, 211, 138, 0.18); animation: mm-pulse 2s infinite; }
.mm-dot.warn { background: var(--mm-warn); box-shadow: 0 0 0 3px rgba(245, 181, 68, 0.16); }
.mm-dot.down { background: var(--mm-down); }
@keyframes mm-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }

/* ---------- Generic card ---------- */
.mm-card {
  border: 1px solid var(--mm-line) !important;
  border-radius: var(--mm-radius) !important;
  background: linear-gradient(180deg, var(--mm-panel-2), var(--mm-panel)) !important;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.03) inset, 0 14px 36px rgba(0, 0, 0, 0.35);
}
.mm-card-head {
  display: flex; align-items: center; justify-content: space-between; gap: 0.75rem;
  margin-bottom: 0.75rem;
}
.mm-card-title { font-size: 0.92rem; font-weight: 700; color: var(--mm-text); letter-spacing: -0.01em; }
.mm-card-sub { font-size: 0.74rem; color: var(--mm-muted); margin-top: 0.1rem; }
.mm-kicker {
  font-size: 0.66rem; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--mm-muted);
}

/* ---------- Quote header + controls ---------- */
.mm-hero-row { align-items: stretch !important; margin-bottom: 1rem !important; }
.mm-quote { padding: 1.1rem 1.3rem; height: 100%; display: flex; gap: 1.2rem; align-items: center; justify-content: space-between; flex-wrap: wrap; }
.mm-quote-id { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.45rem; }
.mm-ticker-badge {
  font-family: var(--mm-mono); font-weight: 700; font-size: 0.8rem;
  padding: 0.18rem 0.5rem; border-radius: 7px;
  background: rgba(124, 140, 255, 0.14); color: #b9c2ff; border: 1px solid rgba(124, 140, 255, 0.35);
}
.mm-quote-name { color: var(--mm-sub); font-size: 0.86rem; font-weight: 500; }
.mm-quote-price-row { display: flex; align-items: baseline; gap: 0.85rem; flex-wrap: wrap; }
.mm-quote-price { font-family: var(--mm-mono); font-size: 2.35rem; font-weight: 700; letter-spacing: -0.03em; color: var(--mm-text); line-height: 1.05; }
.mm-quote-ccy { font-size: 0.8rem; color: var(--mm-muted); font-weight: 600; margin-left: 0.25rem; }
.mm-change {
  font-family: var(--mm-mono); font-weight: 600; font-size: 0.9rem;
  padding: 0.2rem 0.55rem; border-radius: 8px;
}
.mm-change.up { color: var(--mm-up); background: rgba(47, 211, 138, 0.12); }
.mm-change.down { color: var(--mm-down); background: rgba(255, 93, 93, 0.12); }
.mm-change.flat { color: var(--mm-muted); background: rgba(134, 145, 163, 0.12); }
.mm-quote-meta { margin-top: 0.5rem; color: var(--mm-muted); font-size: 0.75rem; }
.mm-spark { flex: 0 0 auto; }

.mm-controls { padding: 1rem 1.1rem !important; gap: 0.7rem !important; justify-content: center; }
.mm-controls .mm-ctl-label { display: flex; justify-content: space-between; align-items: center; }
.mm-controls .mm-ctl-hint { font-size: 0.72rem; color: var(--mm-muted); }
.mm-controls > div { background: transparent !important; border: none !important; }

/* Segmented controls (Gradio Radio restyled) */
.mm-seg, .mm-seg > div, .mm-seg fieldset { background: transparent !important; border: none !important; padding: 0 !important; box-shadow: none !important; }
.mm-seg .wrap {
  display: inline-flex !important; flex-wrap: nowrap !important; gap: 2px !important;
  padding: 3px !important; border-radius: 10px !important;
  background: #0a0e15 !important; border: 1px solid var(--mm-line) !important;
}
.mm-seg label {
  margin: 0 !important; padding: 0.38rem 0.8rem !important;
  border: none !important; border-radius: 8px !important;
  background: transparent !important; box-shadow: none !important;
  color: var(--mm-muted) !important; font-size: 0.78rem !important; font-weight: 600 !important;
  cursor: pointer; transition: background 0.15s ease, color 0.15s ease;
  min-width: 0 !important;
}
.mm-seg label:hover { color: var(--mm-text) !important; background: rgba(255, 255, 255, 0.04) !important; }
.mm-seg label.selected, .mm-seg label:has(input:checked) {
  background: linear-gradient(180deg, #232c3b, #1a2230) !important;
  color: var(--mm-text) !important;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.06) inset, 0 2px 8px rgba(0, 0, 0, 0.4) !important;
}
.mm-seg input[type="radio"] { display: none !important; }
.mm-seg-full .wrap { display: flex !important; width: 100%; }
.mm-seg-full label { flex: 1 1 0; justify-content: center; text-align: center; }

.mm-run-btn {
  min-height: 44px !important; border-radius: 10px !important;
  font-weight: 700 !important; font-size: 0.92rem !important; letter-spacing: 0.01em;
  color: #0b0f1a !important; border: none !important;
  background: linear-gradient(135deg, #9aa6ff, var(--mm-brand) 45%, var(--mm-brand-2)) !important;
  box-shadow: 0 10px 26px rgba(124, 140, 255, 0.32) !important;
  transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease !important;
}
.mm-run-btn:hover { transform: translateY(-1px); filter: brightness(1.06); box-shadow: 0 14px 32px rgba(124, 140, 255, 0.42) !important; }
.mm-run-btn:disabled { filter: grayscale(0.4) brightness(0.8); transform: none; cursor: progress; }

/* ---------- Disclaimer strip ---------- */
.mm-disclaimer {
  display: flex; gap: 0.75rem; align-items: flex-start;
  margin: 0 0 1rem; padding: 0.7rem 0.95rem;
  border: 1px solid rgba(245, 181, 68, 0.28); border-radius: 12px;
  background: linear-gradient(90deg, rgba(245, 181, 68, 0.09), rgba(245, 181, 68, 0.02));
  color: #d9cfb5; font-size: 0.8rem; line-height: 1.5;
}
.mm-disclaimer b { color: var(--mm-warn); }
.mm-disclaimer svg { flex: 0 0 auto; margin-top: 0.1rem; }

/* ---------- Chart card ---------- */
.mm-chart-card { padding: 1rem 1rem 0.4rem !important; gap: 0.25rem !important; }
.mm-chart-head { align-items: center !important; justify-content: space-between !important; flex-wrap: wrap !important; gap: 0.5rem !important; }
.mm-chart-head > div { flex: 0 1 auto !important; min-width: 0 !important; }
.mm-chart-legend { display: flex; gap: 0.9rem; margin-top: 0.3rem; font-size: 0.72rem; color: var(--mm-muted); }
.mm-chart-legend i { display: inline-block; width: 14px; height: 2px; border-radius: 2px; margin-right: 0.35rem; vertical-align: middle; }
.mm-plot, .mm-plot > div { background: transparent !important; border: none !important; box-shadow: none !important; }
.mm-plot .modebar-container { display: none !important; }

/* ---------- KPI tiles ---------- */
.mm-kpis { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0.65rem; }
@media (max-width: 1100px) { .mm-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 600px) { .mm-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.mm-kpi {
  padding: 0.75rem 0.85rem; border-radius: 12px;
  border: 1px solid var(--mm-line); background: var(--mm-panel);
}
.mm-kpi-label { font-size: 0.66rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--mm-muted); }
.mm-kpi-value { margin-top: 0.3rem; font-family: var(--mm-mono); font-size: 1.08rem; font-weight: 600; color: var(--mm-text); }
.mm-kpi-value.up { color: var(--mm-up); }
.mm-kpi-value.down { color: var(--mm-down); }
.mm-kpi-hint { margin-top: 0.2rem; font-size: 0.7rem; color: var(--mm-muted); }
.mm-range { position: relative; height: 4px; margin-top: 0.55rem; border-radius: 4px; background: linear-gradient(90deg, rgba(255,93,93,0.5), rgba(245,181,68,0.5), rgba(47,211,138,0.5)); }
.mm-range span { position: absolute; top: -3px; width: 10px; height: 10px; margin-left: -5px; border-radius: 50%; background: var(--mm-text); box-shadow: 0 0 0 3px rgba(8, 11, 17, 0.9); }

/* ---------- Verdict ---------- */
.mm-verdict { padding: 1.1rem 1.15rem; position: relative; overflow: hidden; }
.mm-verdict::before {
  content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
  background: var(--mm-muted);
}
.mm-verdict.buy::before { background: linear-gradient(90deg, var(--mm-up), transparent); }
.mm-verdict.hold::before { background: linear-gradient(90deg, var(--mm-warn), transparent); }
.mm-verdict.sell::before { background: linear-gradient(90deg, var(--mm-down), transparent); }
.mm-verdict.idle::before { background: linear-gradient(90deg, var(--mm-brand), transparent); }
.mm-verdict-main { display: flex; justify-content: space-between; align-items: center; gap: 1rem; margin-top: 0.55rem; }
.mm-verdict-rec { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.04em; line-height: 1; }
.mm-verdict.buy .mm-verdict-rec { color: var(--mm-up); }
.mm-verdict.hold .mm-verdict-rec { color: var(--mm-warn); }
.mm-verdict.sell .mm-verdict-rec { color: var(--mm-down); }
.mm-verdict.idle .mm-verdict-rec { color: var(--mm-text); font-size: 1.7rem; }
.mm-verdict-tag { margin-top: 0.35rem; color: var(--mm-sub); font-size: 0.84rem; }
.mm-verdict-explain { margin-top: 0.85rem; color: var(--mm-sub); font-size: 0.82rem; line-height: 1.55; }
.mm-consensus { margin-top: 0.95rem; }
.mm-consensus-bar { display: flex; height: 8px; border-radius: 6px; overflow: hidden; background: #0a0e15; border: 1px solid var(--mm-line); margin-top: 0.45rem; }
.mm-consensus-bar span { display: block; height: 100%; }
.mm-consensus-legend { display: flex; flex-wrap: wrap; gap: 0.8rem; margin-top: 0.45rem; font-size: 0.72rem; color: var(--mm-muted); }
.mm-consensus-legend b { color: var(--mm-text); font-family: var(--mm-mono); font-weight: 600; }
.mm-sw { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 0.3rem; }

/* ---------- Agent pipeline ---------- */
.mm-pipeline { padding: 1rem 1.05rem; }
.mm-pipe-row {
  display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; gap: 0.65rem; align-items: center;
  padding: 0.62rem 0; border-top: 1px solid var(--mm-line);
}
.mm-pipe-row:first-of-type { border-top: none; }
.mm-pipe-icon {
  width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center;
  font-size: 0.74rem; font-weight: 700; color: var(--mm-text);
  background: #1a2130; border: 1px solid var(--mm-line-2);
}
.mm-pipe-name { font-size: 0.84rem; font-weight: 600; color: var(--mm-text); }
.mm-pipe-role { font-size: 0.7rem; color: var(--mm-muted); margin-top: 0.08rem; }
.mm-pipe-meter { height: 3px; margin-top: 0.4rem; border-radius: 3px; background: #0a0e15; overflow: hidden; }
.mm-pipe-meter span { display: block; height: 100%; border-radius: 3px; }
.mm-pipe-right { text-align: right; }
.mm-pipe-conf { font-family: var(--mm-mono); font-size: 0.7rem; color: var(--mm-muted); margin-top: 0.2rem; }

.mm-pill {
  display: inline-block; padding: 0.16rem 0.5rem; border-radius: 6px;
  font-size: 0.68rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
  border: 1px solid var(--mm-line-2); color: var(--mm-muted); background: rgba(134, 145, 163, 0.08);
}
.mm-pill.pos { color: var(--mm-up); border-color: rgba(47, 211, 138, 0.4); background: rgba(47, 211, 138, 0.1); }
.mm-pill.neg { color: var(--mm-down); border-color: rgba(255, 93, 93, 0.4); background: rgba(255, 93, 93, 0.1); }
.mm-pill.mid { color: var(--mm-warn); border-color: rgba(245, 181, 68, 0.38); background: rgba(245, 181, 68, 0.1); }
.mm-pill.ok { color: var(--mm-brand-2); border-color: rgba(79, 209, 255, 0.35); background: rgba(79, 209, 255, 0.08); }

/* ---------- Brief + headlines ---------- */
.mm-brief { padding: 1.1rem 1.25rem; height: 100%; }
.mm-brief h2 { margin: 0.45rem 0 0.5rem; font-size: 1.25rem; font-weight: 700; letter-spacing: -0.02em; color: var(--mm-text); }
.mm-brief h2.buy { color: var(--mm-up); }
.mm-brief h2.hold { color: var(--mm-warn); }
.mm-brief h2.sell { color: var(--mm-down); }
.mm-brief p { margin: 0; color: var(--mm-sub); font-size: 0.86rem; line-height: 1.6; }
.mm-brief ul { margin: 0.8rem 0 0; padding: 0; list-style: none; }
.mm-brief li {
  position: relative; padding: 0.42rem 0 0.42rem 1.1rem;
  border-top: 1px dashed var(--mm-line); color: var(--mm-sub); font-size: 0.83rem; line-height: 1.45;
}
.mm-brief li::before { content: ""; position: absolute; left: 0.1rem; top: 0.95rem; width: 6px; height: 6px; border-radius: 2px; background: var(--mm-brand); }
.mm-brief-note { margin-top: 0.85rem !important; font-size: 0.72rem !important; color: var(--mm-muted) !important; }

.mm-news { padding: 1.1rem 1.15rem; height: 100%; }
.mm-news-item { padding: 0.6rem 0; border-top: 1px solid var(--mm-line); }
.mm-news-item:first-of-type { border-top: none; padding-top: 0.2rem; }
.mm-news-title { color: var(--mm-text); font-size: 0.83rem; font-weight: 500; line-height: 1.4; }
.mm-news-meta { margin-top: 0.22rem; color: var(--mm-muted); font-size: 0.7rem; }
.mm-empty { color: var(--mm-muted); font-size: 0.82rem; padding: 0.6rem 0; }

/* ---------- Specialist reports ---------- */
.mm-section-head { display: flex; align-items: baseline; justify-content: space-between; margin: 0.4rem 0 0.7rem; }
.mm-section-title { font-size: 1rem; font-weight: 700; color: var(--mm-text); letter-spacing: -0.01em; }
.mm-reports { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.8rem; }
@media (max-width: 1100px) { .mm-reports { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .mm-reports { grid-template-columns: 1fr; } }
.mm-report { padding: 1rem 1.05rem; display: flex; flex-direction: column; gap: 0.55rem; }
.mm-report-top { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
.mm-report-name { font-size: 0.86rem; font-weight: 700; color: var(--mm-text); }
.mm-report-role { font-size: 0.7rem; color: var(--mm-muted); }
.mm-report-body { color: var(--mm-sub); font-size: 0.8rem; line-height: 1.55; white-space: pre-wrap; }

/* ---------- Footer ---------- */
.mm-footer { margin-top: 1.6rem; padding-top: 1.3rem; border-top: 1px solid var(--mm-line); }
.mm-sources { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; margin-top: 0.7rem; }
@media (max-width: 1000px) { .mm-sources { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .mm-sources { grid-template-columns: 1fr; } }
.mm-source { padding: 0.85rem 0.95rem; border: 1px solid var(--mm-line); border-radius: 12px; background: var(--mm-panel); }
.mm-source-name { display: flex; justify-content: space-between; align-items: center; gap: 0.4rem; font-size: 0.84rem; font-weight: 700; color: var(--mm-text); }
.mm-source-use { margin-top: 0.35rem; font-size: 0.76rem; color: var(--mm-sub); line-height: 1.45; }
.mm-source-by { margin-top: 0.4rem; font-size: 0.7rem; color: var(--mm-muted); }
.mm-footer code {
  font-family: var(--mm-mono); font-size: 0.7rem; color: #b9c2ff;
  background: rgba(124, 140, 255, 0.1); padding: 0.05rem 0.3rem; border-radius: 4px;
}
.mm-legal {
  margin-top: 1rem; padding: 0.95rem 1.05rem; border-radius: 12px;
  border: 1px solid var(--mm-line); background: rgba(15, 20, 28, 0.6);
  color: var(--mm-muted); font-size: 0.74rem; line-height: 1.6;
}
.mm-legal b { color: var(--mm-sub); }
.mm-copy { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.9rem; color: var(--mm-muted); font-size: 0.7rem; }
"""


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------
def _signal_class(signal: str) -> str:
    return (signal or "unavailable").strip().lower().replace(" ", "-")


def _tone(signal: str | None) -> str:
    """Map any agent signal to a pill tone: pos / neg / mid / none."""
    signal = (signal or "").strip().lower()
    if signal in {"bullish", "buy", "low"}:
        return "pos"
    if signal in {"bearish", "sell", "high"}:
        return "neg"
    if signal in {"neutral", "hold", "medium"}:
        return "mid"
    return ""


_TONE_COLOR = {"pos": _UP, "neg": _DOWN, "mid": _WARN, "": "#3a4456"}


def _format_pct(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value * 100:+.{digits}f}%"


def _format_number(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:,.{digits}f}"


def _direction(value: Optional[float]) -> str:
    if value is None or abs(value) < 1e-9:
        return "flat"
    return "up" if value > 0 else "down"


def _pct_change(closes: list[float], lookback: int) -> Optional[float]:
    if len(closes) <= lookback:
        return None
    base = closes[-1 - lookback]
    return (closes[-1] / base - 1.0) if base else None


def _market_session(now: Optional[datetime] = None) -> tuple[str, str]:
    """Approximate US equity session from New York time (ignores holidays)."""
    now = (now or datetime.now(_NY)).astimezone(_NY)
    if now.weekday() >= 5:
        return "down", "Market closed"
    t = now.time()
    if time(9, 30) <= t < time(16, 0):
        return "up", "Market open"
    if time(4, 0) <= t < time(9, 30):
        return "warn", "Pre-market"
    if time(16, 0) <= t < time(20, 0):
        return "warn", "After hours"
    return "down", "Market closed"


def _sparkline_svg(values: list[float], width: int = 180, height: int = 56) -> str:
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    step = width / (len(values) - 1)
    points = [
        (i * step, height - 3 - (v - lo) / span * (height - 6))
        for i, v in enumerate(values)
    ]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area = f"M0,{height} L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + f" L{width},{height} Z"
    color = _UP if values[-1] >= values[0] else _DOWN
    lx, ly = points[-1]
    return f"""
<svg class="mm-spark" width="{width}" height="{height}" viewBox="0 0 {width} {height}" aria-hidden="true">
  <defs>
    <linearGradient id="mmSparkFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{color}" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="{color}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <path d="{area}" fill="url(#mmSparkFill)"/>
  <polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>
  <circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="{color}"/>
</svg>"""


def _confidence_ring(value: Optional[float], color: str, size: int = 92) -> str:
    """SVG confidence gauge (0.0 – 1.0); ``None`` renders an empty ring."""
    radius = 38
    circumference = 2 * 3.14159265 * radius
    if value is None:
        arc = ""
        label = "—"
    else:
        value = max(0.0, min(1.0, float(value)))
        offset = circumference * (1 - value)
        arc = (
            f'<circle cx="46" cy="46" r="{radius}" fill="none" stroke="{color}" stroke-width="7" '
            f'stroke-linecap="round" stroke-dasharray="{circumference:.1f}" '
            f'stroke-dashoffset="{offset:.1f}" transform="rotate(-90 46 46)"/>'
        )
        label = f"{int(round(value * 100))}"
    return f"""
<svg width="{size}" height="{size}" viewBox="0 0 92 92" role="img" aria-label="Confidence {label}">
  <circle cx="46" cy="46" r="{radius}" fill="none" stroke="{_LINE}" stroke-width="7"/>
  {arc}
  <text x="46" y="48" text-anchor="middle" fill="{_TEXT}" font-family="JetBrains Mono, monospace" font-size="20" font-weight="600">{label}</text>
  <text x="46" y="63" text-anchor="middle" fill="{_MUTED}" font-family="Inter, sans-serif" font-size="8" letter-spacing="1.2">CONF %</text>
</svg>"""


# --------------------------------------------------------------------------
# Top bar + disclaimer
# --------------------------------------------------------------------------
_LOGO_SVG = """
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
  <path d="M3 17l5-6 4 4 8-10" stroke="#0b0f1a" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="20" cy="5" r="2" fill="#0b0f1a"/>
</svg>"""


def _header_html() -> str:
    tone, session = _market_session()
    ny_now = datetime.now(_NY).strftime("%a %b %d · %H:%M ET")
    llm = bool(os.getenv("OPENAI_API_KEY"))
    sentiment_chip = (
        '<span class="mm-chip"><span class="mm-dot up"></span>Sentiment <b>LLM</b></span>'
        if llm
        else '<span class="mm-chip"><span class="mm-dot warn"></span>Sentiment <b>Keyword</b></span>'
    )
    return f"""
<div class="mm-topbar">
  <div class="mm-brand">
    <div class="mm-logo">{_LOGO_SVG}</div>
    <span class="mm-brand-name">MarketMind</span>
    <span class="mm-brand-tag">S&amp;P 500 · Multi-agent</span>
  </div>
  <div class="mm-status">
    <span class="mm-chip" title="Approximate NYSE session; exchange holidays are not modelled">
      <span class="mm-dot {tone}"></span><b>{session}</b> · {ny_now}
    </span>
    <span class="mm-chip">Data <b>Yahoo Finance</b></span>
    {sentiment_chip}
  </div>
</div>"""


_WARN_ICON = """
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
  <path d="M12 3l9.5 17h-19L12 3z" stroke="#f5b544" stroke-width="2" stroke-linejoin="round"/>
  <path d="M12 10v4.5M12 17.5v.01" stroke="#f5b544" stroke-width="2" stroke-linecap="round"/>
</svg>"""


def _disclaimer_banner_html() -> str:
    """Prominent disclaimer shown near the top of the dashboard."""
    return f"""
<div class="mm-disclaimer" role="note" aria-label="Important disclaimer">
  {_WARN_ICON}
  <div>
    <b>Not financial advice.</b> MarketMind produces educational predictions for an
    academic course project only. It never advises anyone to buy or sell any stock or ETF,
    and it is <b>not responsible</b> for any profit, loss, or outcome from decisions based on
    these results. Do your own research or consult a licensed professional.
  </div>
</div>"""


# --------------------------------------------------------------------------
# Quote header
# --------------------------------------------------------------------------
def _quote_html(data: DataAgentResult, intraday: Optional[pd.DataFrame] = None) -> str:
    if not data.price_history:
        return _idle_quote("No price data returned for this symbol.")

    closes = [bar.close for bar in data.price_history]
    last = closes[-1]
    prev = closes[-2] if len(closes) > 1 else last
    change = last - prev
    change_pct = (last / prev - 1.0) if prev else 0.0
    direction = _direction(change_pct)

    info = data.company_info
    name = html.escape((info.company_name if info else None) or "S&P 500 proxy")
    exchange = html.escape((info.exchange if info else None) or "NYSE Arca")
    currency = html.escape((info.currency if info else None) or "USD")
    as_of = data.price_history[-1].date.strftime("%b %d, %Y")

    intraday_note = ""
    if intraday is not None and not intraday.empty:
        latest = float(intraday["Price"].iloc[-1])
        stamp = pd.Timestamp(intraday["date"].iloc[-1])
        intraday_note = (
            f" · Latest 5-min bar <span class='mm-num'>{latest:,.2f}</span>"
            f" at {stamp.strftime('%H:%M')}"
        )

    return f"""
<div class="mm-quote">
  <div>
    <div class="mm-quote-id">
      <span class="mm-ticker-badge">{html.escape(data.ticker)}</span>
      <span class="mm-quote-name">{name}</span>
    </div>
    <div class="mm-quote-price-row">
      <span class="mm-quote-price">{last:,.2f}<span class="mm-quote-ccy">{currency}</span></span>
      <span class="mm-change {direction}">{change:+,.2f} ({_format_pct(change_pct)})</span>
    </div>
    <div class="mm-quote-meta">{exchange} · Daily close {as_of}{intraday_note}</div>
  </div>
  {_sparkline_svg(closes[-60:])}
</div>"""


def _idle_quote(message: str = "Run an analysis to load live S&P 500 data.") -> str:
    return f"""
<div class="mm-quote">
  <div>
    <div class="mm-quote-id">
      <span class="mm-ticker-badge">{html.escape(SP500_SYMBOL)}</span>
      <span class="mm-quote-name">SPDR S&amp;P 500 ETF · S&amp;P 500 proxy</span>
    </div>
    <div class="mm-quote-price-row">
      <span class="mm-quote-price" style="color:{_MUTED}">—.——</span>
      <span class="mm-change flat">awaiting data</span>
    </div>
    <div class="mm-quote-meta">{html.escape(message)}</div>
  </div>
</div>"""


# --------------------------------------------------------------------------
# Verdict + consensus
# --------------------------------------------------------------------------
_DECISION_TAGLINES = {
    "BUY": "Evidence leans positive",
    "HOLD": "Evidence is mixed",
    "SELL": "Evidence leans negative",
}
_REC_COLOR = {"BUY": _UP, "HOLD": _WARN, "SELL": _DOWN}


def _consensus_html(results: list[AgentResult]) -> str:
    counts = {"pos": 0, "mid": 0, "neg": 0, "": 0}
    for name, _, _ in _SPECIALISTS[:3]:
        agent = _agent_by_name(results, name)
        counts[_tone(agent.signal if agent else None)] += 1
    total = sum(counts.values()) or 1
    segments = "".join(
        f'<span style="width:{counts[key] / total * 100:.1f}%;background:{_TONE_COLOR[key]}"></span>'
        for key in ("pos", "mid", "neg", "")
        if counts[key]
    )
    legend = "".join(
        f'<span><i class="mm-sw" style="background:{_TONE_COLOR[key]}"></i>{label} <b>{counts[key]}</b></span>'
        for key, label in (("pos", "Bullish"), ("mid", "Neutral"), ("neg", "Bearish"), ("", "No vote"))
    )
    return f"""
<div class="mm-consensus">
  <div class="mm-kicker">Specialist consensus</div>
  <div class="mm-consensus-bar">{segments}</div>
  <div class="mm-consensus-legend">{legend}</div>
</div>"""


def _decision_html(final: FinalRecommendation) -> str:
    rec = final.recommendation.upper()
    css = _signal_class(rec)
    tagline = _DECISION_TAGLINES.get(rec, "Coordinated signal")
    return f"""
<div class="mm-card mm-verdict {css}">
  <div class="mm-kicker">Coordinator verdict · {final.horizon_days}-day horizon</div>
  <div class="mm-verdict-main">
    <div>
      <div class="mm-verdict-rec">{html.escape(rec)}</div>
      <div class="mm-verdict-tag">{html.escape(tagline)}</div>
    </div>
    {_confidence_ring(final.confidence, _REC_COLOR.get(rec, _BRAND))}
  </div>
  {_consensus_html(final.agent_results)}
  <div class="mm-verdict-explain">{html.escape(final.explanation)}</div>
</div>"""


def _idle_decision() -> str:
    return f"""
<div class="mm-card mm-verdict idle">
  <div class="mm-kicker">Coordinator verdict</div>
  <div class="mm-verdict-main">
    <div>
      <div class="mm-verdict-rec">Awaiting run</div>
      <div class="mm-verdict-tag">BUY · HOLD · SELL with confidence</div>
    </div>
    {_confidence_ring(None, _BRAND)}
  </div>
  <div class="mm-verdict-explain">
    The coordinator weighs Technical, Sentiment, and Fundamental votes, then applies the
    Risk overlay and guardrails before issuing one recommendation.
  </div>
</div>"""


def _error_decision(exc: Exception) -> str:
    return f"""
<div class="mm-card mm-verdict sell">
  <div class="mm-kicker">Analysis failed</div>
  <div class="mm-verdict-main"><div><div class="mm-verdict-rec" style="font-size:1.6rem">Error</div>
  <div class="mm-verdict-tag">{html.escape(type(exc).__name__)}</div></div></div>
  <div class="mm-verdict-explain">{html.escape(str(exc))}</div>
</div>"""


# --------------------------------------------------------------------------
# Agent pipeline
# --------------------------------------------------------------------------
def _agent_by_name(results: list[AgentResult], name: str) -> AgentResult | None:
    for result in results:
        if result.agent_name == name:
            return result
    return None


def _pipe_row(icon: str, name: str, role: str, pill: str, tone: str, conf: Optional[float]) -> str:
    width = 0.0 if conf is None else max(0.0, min(1.0, conf)) * 100
    conf_text = "—" if conf is None else f"{conf:.2f}"
    return f"""
<div class="mm-pipe-row">
  <div class="mm-pipe-icon">{icon}</div>
  <div>
    <div class="mm-pipe-name">{html.escape(name)}</div>
    <div class="mm-pipe-role">{html.escape(role)}</div>
    <div class="mm-pipe-meter"><span style="width:{width:.0f}%;background:{_TONE_COLOR[tone]}"></span></div>
  </div>
  <div class="mm-pipe-right">
    <span class="mm-pill {tone}">{html.escape(pill)}</span>
    <div class="mm-pipe-conf">conf {conf_text}</div>
  </div>
</div>"""


def _pipeline_html(
    final: Optional[FinalRecommendation] = None,
    data: Optional[DataAgentResult] = None,
) -> str:
    if data is not None:
        data_row = f"""
<div class="mm-pipe-row">
  <div class="mm-pipe-icon">DA</div>
  <div>
    <div class="mm-pipe-name">Data</div>
    <div class="mm-pipe-role">{data.records_count} daily bars · {len(data.news)} headlines · fundamentals {"✓" if data.fundamentals else "—"}</div>
  </div>
  <div class="mm-pipe-right"><span class="mm-pill ok">Loaded</span></div>
</div>"""
    else:
        data_row = _pipe_row("DA", "Data", "Prices · fundamentals · news", "Idle", "", None)

    rows = [data_row]
    for name, title, role in _SPECIALISTS:
        agent = _agent_by_name(final.agent_results, name) if final else None
        if agent is None:
            rows.append(_pipe_row(title[:2].upper(), title, role, "Idle" if final is None else "N/A", "", None))
            continue
        signal = agent.signal.strip().lower()
        conf = None if signal == "unavailable" else float(agent.confidence)
        rows.append(_pipe_row(title[:2].upper(), title, role, signal, _tone(signal), conf))

    return f"""
<div class="mm-card mm-pipeline">
  <div class="mm-card-head">
    <div>
      <div class="mm-card-title">Agent pipeline</div>
      <div class="mm-card-sub">DataAgent feeds every specialist</div>
    </div>
  </div>
  {"".join(rows)}
</div>"""


# --------------------------------------------------------------------------
# KPI tiles
# --------------------------------------------------------------------------
def _kpi(label: str, value: str, hint: str, css: str = "", extra: str = "") -> str:
    return f"""
<div class="mm-kpi">
  <div class="mm-kpi-label">{html.escape(label)}</div>
  <div class="mm-kpi-value {css}">{value}</div>
  {extra}
  <div class="mm-kpi-hint">{hint}</div>
</div>"""


def _snapshot_html(data: DataAgentResult) -> str:
    if not data.price_history:
        return _idle_snapshot()

    closes = [bar.close for bar in data.price_history]
    last = closes[-1]
    d1 = _pct_change(closes, 1)
    d5 = _pct_change(closes, 5)
    m1 = _pct_change(closes, 21)

    fund = data.fundamentals
    year = closes[-252:]
    hi = (fund.fifty_two_week_high if fund else None) or max(year)
    lo = (fund.fifty_two_week_low if fund else None) or min(year)
    pos = (last - lo) / (hi - lo) if hi > lo else 0.5
    pos = max(0.0, min(1.0, pos))
    range_bar = f'<div class="mm-range"><span style="left:{pos * 100:.0f}%"></span></div>'

    returns = pd.Series(closes).pct_change().dropna()
    annual_vol = float(returns.std(ddof=1)) * (252 ** 0.5) if len(returns) > 1 else None

    pe = fund.trailing_pe if fund else None
    dy = fund.dividend_yield if fund else None
    if dy is not None and dy > 1:
        dy = dy / 100.0
    dy_text = f"Yield {dy:.2%}" if dy is not None else "Yield —"

    tiles = [
        _kpi("1-day", _format_pct(d1), "vs prior close", _direction(d1)),
        _kpi("5-day", _format_pct(d5), "≈ prediction horizon", _direction(d5)),
        _kpi("1-month", _format_pct(m1), "21 trading days", _direction(m1)),
        _kpi(
            "52-week range",
            f"{pos:.0%}",
            f"<span class='mm-num'>{_format_number(lo, 0)} – {_format_number(hi, 0)}</span>",
            extra=range_bar,
        ),
        _kpi(
            "Annual volatility",
            "—" if annual_vol is None else f"{annual_vol:.1%}",
            "from daily returns",
        ),
        _kpi("Trailing P/E", _format_number(pe, 1), dy_text),
    ]
    return f'<div class="mm-kpis">{"".join(tiles)}</div>'


def _idle_snapshot() -> str:
    tiles = [
        _kpi(label, "—", hint)
        for label, hint in (
            ("1-day", "vs prior close"),
            ("5-day", "≈ prediction horizon"),
            ("1-month", "21 trading days"),
            ("52-week range", "position in range"),
            ("Annual volatility", "from daily returns"),
            ("Trailing P/E", "Yield —"),
        )
    ]
    return f'<div class="mm-kpis">{"".join(tiles)}</div>'


# --------------------------------------------------------------------------
# Analyst brief + headlines
# --------------------------------------------------------------------------
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
            f"Over the next ~{horizon_days} trading days the model expects upside "
            "to outweigh downside for the S&P 500."
        )
    elif rec == "SELL":
        base = (
            f"Over the next ~{horizon_days} trading days the model expects downside "
            "pressure on the S&P 500."
        )
    else:
        base = (
            f"Over the next ~{horizon_days} trading days the signals are mixed and "
            "no clear direction stands out."
        )
    if risk == "high":
        return base + " The risk overlay is HIGH, which lowers conviction."
    if risk == "low":
        return base + " The risk overlay looks relatively calm."
    return base + " The risk overlay is moderate."


def _summary_html(final: FinalRecommendation) -> str:
    """Plain-language takeaway panel."""
    rec = (final.recommendation or "HOLD").upper()
    css = _signal_class(rec)
    risk = _agent_by_name(final.agent_results, "risk_agent")
    risk_signal = _signal_phrase(risk.signal if risk else None)
    if risk_signal == "no vote":
        risk_signal = "unknown"

    bullets: list[str] = []
    for name, title, _ in _SPECIALISTS[:3]:
        agent = _agent_by_name(final.agent_results, name)
        if agent and agent.signal != "unavailable":
            bullets.append(f"{title} leans {agent.signal} (confidence {agent.confidence:.2f}).")
        elif agent:
            bullets.append(f"{title} did not vote — inputs were unavailable.")
    if risk and risk.signal != "unavailable":
        bullets.append(f"Risk overlay reads {risk.signal.upper()}.")

    bullet_html = "".join(f"<li>{html.escape(item)}</li>" for item in bullets)
    return f"""
<div class="mm-card mm-brief">
  <div class="mm-kicker">Analyst brief · {html.escape(final.ticker)}</div>
  <h2 class="{css}">{html.escape(_recommendation_headline(rec))}</h2>
  <p>{html.escape(_recommendation_action(rec, final.horizon_days, risk_signal))}</p>
  <ul>{bullet_html}</ul>
  <p class="mm-brief-note">Model output for education only — not a recommendation to trade.</p>
</div>"""


def _idle_summary() -> str:
    return """
<div class="mm-card mm-brief">
  <div class="mm-kicker">Analyst brief</div>
  <h2>Your plain-language takeaway appears here</h2>
  <p>
    After a run you get a one-paragraph summary of what the agents concluded, how each
    specialist voted, and what the risk overlay means for the selected horizon.
  </p>
  <p class="mm-brief-note">Model output for education only — not a recommendation to trade.</p>
</div>"""


def _error_summary(exc: Exception) -> str:
    return f"""
<div class="mm-card mm-brief">
  <div class="mm-kicker">Analyst brief</div>
  <h2 class="sell">Analysis did not finish</h2>
  <p><b>{html.escape(type(exc).__name__)}:</b> {html.escape(str(exc))}</p>
  <p class="mm-brief-note">Check your network connection, then run the analysis again.</p>
</div>"""


def _news_html(data: Optional[DataAgentResult] = None, limit: int = 6) -> str:
    if data is None:
        body = '<div class="mm-empty">Headlines used by the Sentiment agent appear after a run.</div>'
        count = ""
    elif not data.news:
        body = '<div class="mm-empty">No recent headlines were returned by Yahoo Finance.</div>'
        count = "0 items"
    else:
        items = []
        for item in data.news[:limit]:
            meta = html.escape(item.publisher)
            if item.published:
                meta += f" · {html.escape(item.published)}"
            items.append(
                f'<div class="mm-news-item"><div class="mm-news-title">{html.escape(item.title)}</div>'
                f'<div class="mm-news-meta">{meta}</div></div>'
            )
        body = "".join(items)
        count = f"{min(limit, len(data.news))} of {len(data.news)}"
    return f"""
<div class="mm-card mm-news">
  <div class="mm-card-head">
    <div>
      <div class="mm-card-title">Market headlines</div>
      <div class="mm-card-sub">Yahoo Finance news · Sentiment input</div>
    </div>
    <span class="mm-pill">{count or "—"}</span>
  </div>
  {body}
</div>"""


# --------------------------------------------------------------------------
# Specialist reports
# --------------------------------------------------------------------------
def _agent_card_html(title: str, result: AgentResult | None, role: str = "") -> str:
    if result is None:
        signal, conf, body = "idle", None, "Run an analysis to populate this report."
    else:
        signal = result.signal.strip().lower()
        conf = None if signal == "unavailable" else float(result.confidence)
        body = result.explanation
    tone = _tone(signal)
    width = 0.0 if conf is None else max(0.0, min(1.0, conf)) * 100
    return f"""
<div class="mm-card mm-report">
  <div class="mm-report-top">
    <div>
      <div class="mm-report-name">{html.escape(title)}</div>
      <div class="mm-report-role">{html.escape(role)}</div>
    </div>
    <span class="mm-pill {tone}">{html.escape(signal)}</span>
  </div>
  <div class="mm-pipe-meter"><span style="width:{width:.0f}%;background:{_TONE_COLOR[tone]}"></span></div>
  <div class="mm-report-body">{html.escape(body)}</div>
</div>"""


def _reports_html(final: Optional[FinalRecommendation] = None) -> str:
    cards = []
    for name, title, role in _SPECIALISTS:
        agent = _agent_by_name(final.agent_results, name) if final else None
        cards.append(_agent_card_html(title, agent, role))
    return f'<div class="mm-reports">{"".join(cards)}</div>'


# --------------------------------------------------------------------------
# Chart
# --------------------------------------------------------------------------
def _base_layout(fig: go.Figure, height: int = 380) -> None:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=34, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color=_MUTED, size=11),
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=_PANEL,
            bordercolor=_LINE,
            font=dict(family="JetBrains Mono, monospace", color=_TEXT, size=11),
        ),
        dragmode="zoom",
    )


def _empty_chart(message: str = "Run an analysis to load S&P 500 price history.") -> go.Figure:
    fig = go.Figure()
    _base_layout(fig)
    fig.update_layout(
        title=dict(text="", x=0.01),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(color=_MUTED, size=13),
            )
        ],
    )
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
    return daily.tail(days).copy(), f"{window} · daily closes"


def _rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def plot_price_history(
    chart_data: Optional[dict | pd.DataFrame] = None,
    window: str = "1Y",
    frame: Optional[pd.DataFrame] = None,
) -> go.Figure:
    """
    Interactive Plotly chart: Close (gradient area) + SMA20 / SMA50.

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

    first = float(view["Price"].iloc[0])
    last = float(view["Price"].iloc[-1])
    change = (last / first - 1.0) if first else 0.0
    color = _UP if change >= 0 else _DOWN
    lo = float(view[["Price", "SMA20", "SMA50"]].min(numeric_only=True).min())
    hi = float(view[["Price", "SMA20", "SMA50"]].max(numeric_only=True).max())
    pad = (hi - lo) * 0.08 or hi * 0.01
    floor = lo - pad

    intraday = window_key == "1D"
    hover_x = "%H:%M" if intraday else "%b %d, %Y"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=view["date"],
            y=[floor] * len(view),
            mode="lines",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=view["date"],
            y=view["Price"],
            name="Close",
            mode="lines",
            line=dict(color=color, width=2.2),
            fill="tonexty",
            fillcolor=_rgba(color, 0.10),
            fillgradient=dict(
                type="vertical",
                colorscale=[[0.0, _rgba(color, 0.0)], [1.0, _rgba(color, 0.28)]],
            ),
            hovertemplate="Close %{y:,.2f}<extra></extra>",
        )
    )
    for column, line_color, label in (("SMA20", _SMA20, "SMA20"), ("SMA50", _SMA50, "SMA50")):
        if view[column].notna().any():
            fig.add_trace(
                go.Scatter(
                    x=view["date"],
                    y=view[column],
                    name=label,
                    mode="lines",
                    line=dict(color=line_color, width=1.4, dash="dot" if column == "SMA50" else "solid"),
                    hovertemplate=f"{label} %{{y:,.2f}}<extra></extra>",
                )
            )

    fig.add_trace(
        go.Scatter(
            x=[view["date"].iloc[-1]],
            y=[last],
            mode="markers",
            marker=dict(size=8, color=color, line=dict(color=_BG, width=2)),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    _base_layout(fig)
    fig.update_layout(
        title=dict(
            text=(
                f"<span style='color:{_TEXT}'>{title}</span>"
                f"  <span style='color:{color}'>{change:+.2%}</span>"
            ),
            x=0.005,
            y=0.98,
            xanchor="left",
            font=dict(size=12),
        ),
        annotations=[
            dict(
                x=1,
                y=last,
                xref="paper",
                yref="y",
                text=f"<b>{last:,.2f}</b>",
                showarrow=False,
                xanchor="left",
                font=dict(family="JetBrains Mono, monospace", size=11, color=_BG),
                bgcolor=color,
                borderpad=3,
            )
        ],
    )
    fig.update_xaxes(
        showgrid=False,
        showline=False,
        zeroline=False,
        tickfont=dict(color=_MUTED),
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="#4a5568",
        spikethickness=1,
        spikedash="dot",
        hoverformat=hover_x,
        rangebreaks=[] if intraday else [dict(bounds=["sat", "mon"])],
    )
    fig.update_yaxes(
        side="right",
        range=[floor, hi + pad],
        gridcolor=_rgba("#ffffff", 0.05),
        zeroline=False,
        tickformat=",.0f" if hi - lo > 20 else ",.2f",
        tickfont=dict(family="JetBrains Mono, monospace", color=_MUTED),
        showspikes=True,
        spikemode="across",
        spikecolor="#4a5568",
        spikethickness=1,
        spikedash="dot",
    )
    return fig


def _chart_head_html() -> str:
    return f"""
<div>
  <div class="mm-card-title">Price action · {html.escape(SP500_SYMBOL)}</div>
  <div class="mm-chart-legend">
    <span><i style="background:{_UP}"></i>Close</span>
    <span><i style="background:{_SMA20}"></i>SMA 20</span>
    <span><i style="background:{_SMA50}"></i>SMA 50</span>
    <span>· hover for values, drag to zoom, double-click to reset</span>
  </div>
</div>"""


# --------------------------------------------------------------------------
# Footer
# --------------------------------------------------------------------------
def _api_footer_html() -> str:
    """Footer explaining which external APIs power each MarketMind feature."""
    llm = bool(os.getenv("OPENAI_API_KEY"))
    openai_pill = (
        '<span class="mm-pill pos">Active</span>' if llm else '<span class="mm-pill mid">Optional</span>'
    )
    openai_use = (
        "LLM scoring of news headlines for the Sentiment agent."
        if llm
        else "Not configured — Sentiment uses a keyword fallback. Set <code>OPENAI_API_KEY</code> to enable LLM scoring."
    )
    sources = [
        (
            "Yahoo Finance · yfinance",
            '<span class="mm-pill pos">Active</span>',
            "Daily &amp; 5-minute OHLCV prices, fund metadata, fundamental metrics, and news headlines.",
            "DataAgent → Technical, Sentiment, Fundamental, Risk, chart",
        ),
        ("OpenAI API", openai_pill, openai_use, "Sentiment agent"),
        (
            "FastAPI",
            '<span class="mm-pill ok">Service</span>',
            "REST endpoints <code>/health</code> and <code>/analyze/{ticker}</code>.",
            "<code>uvicorn app.main:app</code>",
        ),
        (
            "Gradio + Plotly",
            '<span class="mm-pill ok">UI</span>',
            "This dashboard and its interactive price chart.",
            "<code>python -m app.ui</code>",
        ),
    ]
    cards = "".join(
        f"""
<div class="mm-source">
  <div class="mm-source-name">{name}{pill}</div>
  <div class="mm-source-use">{use}</div>
  <div class="mm-source-by">Used by: {by}</div>
</div>"""
        for name, pill, use, by in sources
    )
    return f"""
<div class="mm-footer">
  <div class="mm-section-head">
    <div class="mm-section-title">APIs &amp; data sources</div>
    <div class="mm-card-sub">Focus symbol <b>{html.escape(SP500_SYMBOL)}</b> (S&amp;P 500 ETF proxy) · no SEC file storage required</div>
  </div>
  <div class="mm-sources">{cards}</div>
  <div class="mm-legal">
    <b>Disclaimer.</b> MarketMind is an academic course demonstration only. Outputs such as
    BUY / HOLD / SELL are educational predictions / model signals, <b>not financial advice</b>.
    This platform does not provide investment, trading, tax, or legal advice, and it does
    <b>not</b> recommend that anyone buy or sell any security. You are solely responsible for
    any decisions you make. The authors, developers, and affiliated institutions accept
    <b>no responsibility or liability</b> for any loss, damage, or consequence arising from use
    of this software or its outputs. Market data may be delayed or incomplete.
  </div>
  <div class="mm-copy">
    <span>MarketMind · CS529 Artificial Intelligence course project</span>
    <span>Data © respective providers · Yahoo Finance data may be delayed</span>
  </div>
</div>"""


# --------------------------------------------------------------------------
# Analyze callbacks
# --------------------------------------------------------------------------
_EMPTY_FRAME_COLUMNS = ["date", "Price", "SMA20", "SMA50"]


async def analyze(ticker: str, horizon_days: int, chart_window: str):
    """Run Coordinator + DataAgent and fill the dashboard."""
    window = chart_window or "1Y"
    try:
        final, data = await asyncio.gather(
            _coordinator.analyze(ticker, horizon_days=int(horizon_days)),
            _data_agent.analyze(ticker),
        )
        daily_frame = build_price_frame(data)
        try:
            intraday_raw = _data_agent.market_data.get_intraday_ohlcv(ticker)
            intraday_frame = build_intraday_frame(intraday_raw)
        except Exception:
            # Daily chart still works if intraday is unavailable (weekends, etc.).
            intraday_frame = pd.DataFrame(columns=_EMPTY_FRAME_COLUMNS)
        chart_bundle = {"daily": daily_frame, "intraday": intraday_frame}
        chart = plot_price_history(chart_bundle, window)
    except Exception as exc:
        return (
            _header_html(),
            _idle_quote(f"{type(exc).__name__}: {exc}"),
            _error_decision(exc),
            _pipeline_html(),
            _idle_snapshot(),
            _empty_chart(f"Chart unavailable: {type(exc).__name__}"),
            None,
            _error_summary(exc),
            _news_html(),
            _reports_html(),
        )

    return (
        _header_html(),
        _quote_html(data, intraday_frame),
        _decision_html(final),
        _pipeline_html(final, data),
        _snapshot_html(data),
        chart,
        chart_bundle,
        _summary_html(final),
        _news_html(data),
        _reports_html(final),
    )


def refresh_chart(chart_data: Optional[dict | pd.DataFrame], chart_window: str):
    """Re-draw the chart for a new window without re-running agents."""
    if chart_data is None:
        return _empty_chart()
    return plot_price_history(chart_data, chart_window or "1Y")


def _start_run():
    return gr.update(value="Analyzing…", interactive=False)


def _end_run():
    return gr.update(value="Run analysis", interactive=True)


# --------------------------------------------------------------------------
# Theme + layout
# --------------------------------------------------------------------------
theme = gr.themes.Base(
    primary_hue="indigo",
    secondary_hue="slate",
    neutral_hue="slate",
    font=gr.themes.GoogleFont("Inter"),
    font_mono=gr.themes.GoogleFont("JetBrains Mono"),
).set(
    body_background_fill=_BG,
    body_background_fill_dark=_BG,
    body_text_color=_TEXT,
    body_text_color_dark=_TEXT,
    background_fill_primary=_PANEL,
    background_fill_primary_dark=_PANEL,
    background_fill_secondary=_BG,
    background_fill_secondary_dark=_BG,
    block_background_fill="transparent",
    block_background_fill_dark="transparent",
    block_border_width="0px",
    block_border_width_dark="0px",
    block_shadow="none",
    block_shadow_dark="none",
    block_padding="0px",
    layout_gap="1rem",
    border_color_primary=_LINE,
    border_color_primary_dark=_LINE,
    color_accent_soft="#1a2230",
    color_accent_soft_dark="#1a2230",
    loader_color=_BRAND,
    loader_color_dark=_BRAND,
)


with gr.Blocks(title="MarketMind · S&P 500 multi-agent terminal") as demo:
    ticker_state = gr.State(SP500_SYMBOL)
    price_frame_state = gr.State(None)

    header_out = gr.HTML(value=_header_html())

    with gr.Row(elem_classes=["mm-hero-row"], equal_height=True):
        with gr.Column(scale=8, elem_classes=["mm-card"]):
            quote_out = gr.HTML(value=_idle_quote())
        with gr.Column(scale=4, min_width=300, elem_classes=["mm-card", "mm-controls"]):
            gr.HTML(
                '<div class="mm-ctl-label"><span class="mm-kicker">Prediction horizon</span>'
                '<span class="mm-ctl-hint">trading days</span></div>'
            )
            horizon_input = gr.Radio(
                choices=[(f"{h} days", h) for h in HORIZONS],
                value=5,
                show_label=False,
                container=False,
                elem_classes=["mm-seg", "mm-seg-full"],
            )
            analyze_button = gr.Button(
                "Run analysis",
                variant="primary",
                elem_classes=["mm-run-btn"],
            )

    gr.HTML(value=_disclaimer_banner_html())

    with gr.Row(equal_height=False):
        with gr.Column(scale=8, min_width=520):
            with gr.Column(elem_classes=["mm-card", "mm-chart-card"]):
                with gr.Row(elem_classes=["mm-chart-head"]):
                    gr.HTML(value=_chart_head_html())
                    chart_window = gr.Radio(
                        choices=CHART_WINDOWS,
                        value="1Y",
                        show_label=False,
                        container=False,
                        elem_classes=["mm-seg"],
                    )
                price_chart = gr.Plot(
                    value=_empty_chart(),
                    show_label=False,
                    container=False,
                    elem_classes=["mm-plot"],
                )
            snapshot_out = gr.HTML(value=_idle_snapshot())
        with gr.Column(scale=4, min_width=320):
            decision_out = gr.HTML(value=_idle_decision())
            pipeline_out = gr.HTML(value=_pipeline_html())

    with gr.Row(equal_height=True):
        with gr.Column(scale=7):
            summary_out = gr.HTML(value=_idle_summary())
        with gr.Column(scale=5):
            news_out = gr.HTML(value=_news_html())

    gr.HTML(
        '<div class="mm-section-head"><div class="mm-section-title">Specialist reports</div>'
        '<div class="mm-card-sub">Full reasoning from each agent</div></div>'
    )
    reports_out = gr.HTML(value=_reports_html())

    gr.HTML(value=_api_footer_html())

    analyze_button.click(
        fn=_start_run,
        outputs=[analyze_button],
        queue=False,
    ).then(
        fn=analyze,
        inputs=[ticker_state, horizon_input, chart_window],
        outputs=[
            header_out,
            quote_out,
            decision_out,
            pipeline_out,
            snapshot_out,
            price_chart,
            price_frame_state,
            summary_out,
            news_out,
            reports_out,
        ],
        show_progress="minimal",
    ).then(
        fn=_end_run,
        outputs=[analyze_button],
        queue=False,
    )

    chart_window.change(
        fn=refresh_chart,
        inputs=[price_frame_state, chart_window],
        outputs=[price_chart],
        show_progress="hidden",
    )

    demo.load(fn=_header_html, outputs=[header_out], queue=False)

    # Open populated: run the default analysis on page load, using the
    # same event chain as the Run button (button state, then analysis).
    demo.load(
        fn=_start_run,
        outputs=[analyze_button],
        queue=False,
    ).then(
        fn=analyze,
        inputs=[ticker_state, horizon_input, chart_window],
        outputs=[
            header_out,
            quote_out,
            decision_out,
            pipeline_out,
            snapshot_out,
            price_chart,
            price_frame_state,
            summary_out,
            news_out,
            reports_out,
        ],
        show_progress="minimal",
    ).then(
        fn=_end_run,
        outputs=[analyze_button],
        queue=False,
    )


if __name__ == "__main__":
    demo.launch(theme=theme, css=_CUSTOM_CSS)
