# MarketMind Agents

This document describes each agent in beginner-friendly language.

Phase 1 only defines placeholder classes for some agents.
The **Data Collector Agent**, **Technical Analysis Agent**, and **Sentiment
Analysis Agent** are implemented. Risk and Coordinator already run a demo.

---

## 1. Data Collector Agent

**Status:** Implemented (market data + company info + recent news)

**Input:**
- Market symbol focused on the S&P 500 (for example `SPY`; aliases like `^GSPC` resolve to `SPY`)
- Optional `start` / `end` dates (`YYYY-MM-DD`)
- Optional `period` (default approximately one year: `1y`)
- Optional `as_of_date` to block future price observations (for later backtesting)

**What it does:**
- Downloads historical OHLCV price data via `MarketDataService` (yfinance)
- Collects basic company information (name, sector, industry, exchange, currency, market cap)
- Fetches recent news headlines via `NewsDataService` (yfinance); a news outage degrades to an empty list instead of failing the data pull
- Normalizes tickers to uppercase and cleans unusable rows
- Returns structured Pydantic output (`DataAgentResult`)

**Output:**
- `ticker`
- `company_info`
- `price_history` (oldest → newest)
- `news` (recent headlines: title, publisher, date, summary)
- `start_date` / `end_date`
- `records_count`

**What it does not do:**
- Technical indicators, sentiment, fundamentals, risk scoring, or BUY/HOLD/SELL decisions

**Who consumes this data:**
- **Technical Agent** → `price_history` (OHLCV)
- **Sentiment Agent** → `news` headlines
- **Risk Agent / Coordinator** → same OHLCV (Coordinator loads DataAgent once, then shares it)
- **Fundamental Agent** → does **not** use DataAgent; it reads SEC filings from its own vector store (company-level RAG). For the S&P 500 (`SPY`) focus, that agent is often `unavailable`.

---

## 2. Technical Analysis Agent

**Status:** Implemented

**Input:**
- Historical OHLCV price data from DataAgent (`list[MarketPrice]` / `DataAgentResult`)
- Does **not** download market data itself

**Analysis:**
- RSI(14)
- SMA20 vs SMA50
- MACD (12 / 26 / 9)
- Volume trend (vs 20-day average; supporting evidence only)
- 5-trading-day price trend

**How the signal is chosen:**
- Each of RSI, SMA crossover, MACD, and 5-day trend votes +1 / 0 / -1
- Score ≥ +2 → `bullish`; score ≤ -2 → `bearish`; otherwise `neutral`
- Confidence grows with |score| and how many votes agree

**Output:**
- Technical signal: `bullish` | `neutral` | `bearish` (never BUY/HOLD/SELL)
- Confidence score (0.0 – 1.0)
- Short explanation built from the indicator values
- Detailed values also available via `TechnicalAnalysisResult`

---

## 3. Sentiment Agent

**Status:** Implemented

**Input:**
- Recent company news headlines from DataAgent (`DataAgentResult.news`, fetched by `NewsDataService`)
- Does **not** download news itself

**Analysis:**
- An LLM scores sentiment using ONLY the supplied headlines, which are numbered in the prompt; every evidence bullet cites its headline (for example `[1]`)
- Headlines are treated as untrusted data, never as instructions
- Model output is parsed deterministically (`SCORE` / `EVIDENCE` / `VERDICT`); score ≥ +0.33 → `bullish`, ≤ −0.33 → `bearish`, otherwise `neutral`
- Too little coverage, a failed data pull, or missing configuration returns `unavailable` (this agent does not vote) instead of raising an error

**Output:**
- Sentiment signal: `bullish` | `neutral` | `bearish` (never BUY/HOLD/SELL)
- Confidence score (0.0 – 1.0, the absolute parsed score)
- Short explanation built from the cited headlines

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
