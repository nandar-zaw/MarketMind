# MarketMind Agents

This document describes each agent in beginner-friendly language.

Phase 1 only defines placeholder classes.
Real analysis will be added in later phases.

---

## 1. Data Collector Agent

**Input:**
- Stock ticker symbol (for example `AAPL`)

**Future analysis:**
- Download historical stock price data
- Collect basic company information
- Prepare clean data for other agents

**Output:**
- Market and company data that other agents can use

---

## 2. Technical Analysis Agent

**Input:**
- Historical stock price data

**Future analysis:**
- RSI
- Moving averages (SMA)
- MACD
- Volume trend
- Short-term price trend

**Output:**
- Technical signal (for example bullish / neutral / bearish)
- Confidence score
- Short explanation

---

## 3. Sentiment Agent

**Input:**
- Recent company news and headlines

**Future analysis:**
- Positive / neutral / negative sentiment
- Summary of recent market mood around the company

**Output:**
- Sentiment signal
- Confidence score
- Short explanation

---

## 4. Fundamental Analysis Agent

**Input:**
- Company financial information

**Future analysis:**
- Revenue growth
- Earnings
- P/E ratio
- Debt levels
- Overall financial health

**Output:**
- Fundamental signal
- Confidence score
- Short explanation

---

## 5. Risk Manager Agent

**Status:** implemented for the classroom demo.

**Input:**
- Price history (Close) from the market-data tool
- Optional signals from other agents (event pressure)

**Analysis:**
- Annualized volatility
- Max drawdown
- 5-day return / latest daily move
- LOW / MEDIUM / HIGH risk level

**Output:**
- `AgentResult` with signal `low` | `medium` | `high`
- Confidence score
- Short explanation

This agent does **not** output BUY/SELL. It is a safety overlay for the Coordinator.

---

## 6. Coordinator Agent

**Status:** implemented for the classroom demo, with guardrails.

**Input:**
- User ticker (checked by an **input guardrail**)
- Price history from `get_price_history` (checked by a **tool guardrail**)
- Results from Technical, Sentiment, Fundamental, and Risk agents

**Analysis:**
- Run specialist agents; unimplemented ones are `unavailable` and do not vote
- Ask Risk Manager to review
- Blend live votes; if Technical is still missing, use a labeled 5-day return context
- **Output guardrail:** HIGH risk cannot remain a BUY

**Output:**
- Final recommendation: **BUY**, **HOLD**, or **SELL**
- Overall confidence score
- Short explanation
- Supporting evidence from each agent
- Guardrail event log (input / tool / output)

**Prediction horizon:** 5 trading days
