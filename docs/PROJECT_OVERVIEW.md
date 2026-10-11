# Project Overview

## Title

**MarketMind:** A Multi-Agent System for Market Trend Prediction and Investment Decision Support  
*(Academic demonstration — not a production trading system.)*

## Problem

Students often see “AI trading” demos that hide how agents coordinate. MarketMind makes the multi-agent pattern explicit: specialized agents vote, a risk overlay protects the decision, and guardrails keep inputs/tools/outputs safe.

## Solution (one paragraph)

A user analyzes a ticker. The **Coordinator** validates input, loads market data once through the **Data Collector Agent**, runs **Technical**, **Sentiment**, and **Fundamental** agents **in parallel** on that shared data, asks **Risk** for a LOW/MEDIUM/HIGH overlay, blends the votes into **BUY / HOLD / SELL**, then applies a **decision output guardrail** (e.g. HIGH risk cannot stay BUY). Results appear in a Gradio dashboard (also mounted on FastAPI at `/`).

## Agent roles

| Agent | Job | Does it BUY/SELL? |
| --- | --- | --- |
| Data Collector | Prices, company info, news, filing excerpts | No |
| Technical | RSI, SMA, MACD, trend | Votes bullish/neutral/bearish |
| Sentiment | News tone (LLM) | Votes |
| Fundamental | SEC filing excerpts (LLM) | Votes |
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

## User interfaces

| File | Chart | Command |
| --- | --- | --- |
| `app/ui.py` | Plotly | `python -m app.ui` |
| `app/ui_gradio_only.py` | Plain SVG in Gradio HTML | `python -m app.ui_gradio_only` |
| FastAPI mount | Main dashboard at `/` | `uvicorn app.main:app --reload` |

## How to run

See the root [`README.md`](../README.md) and [`HOW_TO_RUN.md`](HOW_TO_RUN.md).

## Key code entry points

See [`CODE_MAP.md`](CODE_MAP.md).
