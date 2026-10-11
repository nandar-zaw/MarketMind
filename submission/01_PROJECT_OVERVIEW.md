# 01 — Project Overview

## Title

**MarketMind:** A Multi-Agent System for S&P 500 Trend Prediction and Investment Decision Support  
*(Academic demonstration — not a production trading system.)*

## Problem

Students often see “AI trading” demos that hide how agents coordinate. MarketMind makes the multi-agent pattern explicit: specialized agents vote, a risk overlay protects the decision, and guardrails keep inputs/tools/outputs safe.

## Solution (one paragraph)

A user analyzes a ticker (default **SPY**). The **Coordinator** validates input, loads market data once through the **Data Collector Agent** (Yahoo Finance / yfinance), runs **Technical**, **Sentiment**, and **Fundamental** agents **in parallel** on that shared data, asks **Risk** for a LOW/MEDIUM/HIGH overlay, blends the votes into **BUY / HOLD / SELL**, then applies a **decision output guardrail** (e.g. HIGH risk cannot stay BUY). Results appear in a Gradio dashboard or via FastAPI.

## Agent roles

| Agent | Job | Does it BUY/SELL? |
| --- | --- | --- |
| Data Collector | Prices, fundamentals, news | No |
| Technical | RSI, SMA, MACD, trend | Votes bullish/neutral/bearish |
| Sentiment | News tone (LLM or keyword fallback) | Votes |
| Fundamental | Valuation / growth / quality metrics | Votes |
| Risk | Volatility / drawdown | low / medium / high |
| Coordinator | Blend + final decision | **Yes — BUY/HOLD/SELL** |

## Orchestration pattern

**Coordinator / orchestrator (hybrid):**

1. DataAgent first (sequential)  
2. Three specialists in parallel (fan-out)  
3. Risk after specialists (sequential)  
4. Coordinator decides + output guardrail  

Not a handoff chain: control always returns to the Coordinator.

## Guardrails (classroom pattern)

| Type | Examples |
| --- | --- |
| Input | Empty ticker, injection-like text, bad format |
| Tool | Allowlisted market-data call; enough price rows |
| Output | Valid signals; HIGH risk blocks BUY → HOLD |

Hard fails stop the run (API 400). Soft policies rewrite and continue.

## Data sources

- **Yahoo Finance via yfinance** — OHLCV, `.info` fundamentals, news headlines  
- **OpenAI** (optional) — Sentiment LLM; keyword fallback if no key  

## User interfaces

| File | Chart | Command |
| --- | --- | --- |
| `app/ui.py` | Plotly | `python -m app.ui` |
| `app/ui_gradio_only.py` | Plain SVG in Gradio HTML | `python -m app.ui_gradio_only` |

## Example walkthrough (SPY)

1. User clicks Analyze on SPY (horizon 5 days).  
2. Input guardrail accepts `SPY`.  
3. DataAgent fetches prices / fundamentals / news.  
4. Technical, Sentiment, Fundamental vote in parallel.  
5. Risk scores market risk.  
6. Coordinator blends → e.g. HOLD.  
7. Output guardrail finalizes.  
8. UI shows verdict, chart, agent reports, headlines.

## Status vs roadmap

**Done:** Phases 1–6 agents + guardrails, Phase 9 dual Gradio dashboards, FastAPI analyze.  
**Later:** Phase 7 ML model, Phase 8 backtesting.

## How to run this package

This `submission/` folder is **self-contained**. See [`02_HOW_TO_RUN.md`](02_HOW_TO_RUN.md)
and the cover [`README.md`](README.md).

## Key code entry points

See [`07_CODE_MAP.md`](07_CODE_MAP.md).
