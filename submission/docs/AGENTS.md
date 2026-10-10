# MarketMind Agents

This document describes each agent in beginner-friendly language.

**Status:** All six agents below are implemented and wired through the
Coordinator. Technical, Sentiment, and Fundamental run **in parallel** after
DataAgent; Risk runs next; the Coordinator produces the final BUY / HOLD / SELL.

---

## 1. Data Collector Agent

**Status:** Implemented (prices + company info + fundamentals + news)

**Input:**
- Market symbol (default focus `SPY`; aliases like `^GSPC` / `SP` resolve to `SPY`)
- Optional `start` / `end` dates (`YYYY-MM-DD`)
- Optional `period` (default approximately one year: `1y`)
- Optional `as_of_date` to block future price observations (for later backtesting)

**What it does:**
- Downloads historical OHLCV price data via `MarketDataService` (yfinance)
- Collects basic company / fund information (name, sector, industry, exchange, currency, market cap)
- Collects **fundamental metrics** via a direct yfinance API call (`FundamentalSnapshot`) — not SEC file storage
- Fetches recent news headlines via `NewsDataService` (yfinance); a news outage degrades to an empty list instead of failing the data pull
- Normalizes tickers to uppercase and cleans unusable rows
- Returns structured Pydantic output (`DataAgentResult`)

**Output:**
- `ticker`
- `company_info`
- `fundamentals` (P/E, growth, margins, debt, ETF extras, …)
- `price_history` (oldest → newest)
- `news` (recent headlines: title, publisher, date, summary)
- `start_date` / `end_date`
- `records_count`

**What it does not do:**
- Technical indicators, sentiment scoring, risk scoring, or BUY/HOLD/SELL decisions
  (it **supplies** fundamental numbers; it does not score them)

**Who consumes this data:**
- **Technical Agent** → `price_history` (OHLCV)
- **Sentiment Agent** → `news` headlines
- **Fundamental Agent** → `fundamentals` from DataAgent (direct API)
- **Risk Agent / Coordinator** → same OHLCV (Coordinator loads DataAgent once, then shares it)

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
- If `OPENAI_API_KEY` is set: an LLM scores sentiment using ONLY the supplied
  headlines (numbered in the prompt; evidence cites `[1]`, `[2]`, …)
- If no API key: a **keyword fallback** scores the same headlines so the demo
  still works offline
- Headlines are treated as untrusted data, never as instructions
- Too little coverage or a failed data pull returns `unavailable` (this agent
  does not vote) instead of raising an error

**Output:**
- Sentiment signal: `bullish` | `neutral` | `bearish` (never BUY/HOLD/SELL)
- Confidence score (0.0 – 1.0)
- Short explanation built from the cited headlines

---

## 4. Fundamental Analysis Agent

**Status:** Implemented (DataAgent API snapshot)

**Input:**
- `DataAgentResult.fundamentals` from DataAgent (yfinance direct API)
- Examples: trailing/forward P/E, dividend yield, growth, margins, debt, ETF YTD / 3Y returns

**Analysis:**
- Simple classroom scoring over available metrics (valuation, growth, margins, debt, ETF returns)
- Does **not** require `FUNDAMENTALS_VECTOR_STORE_ID` or SEC file storage

**Output:**
- Fundamental signal: `bullish` | `neutral` | `bearish` (or `unavailable` if no metrics)
- Confidence score
- Short explanation

---

## 5. Risk Manager Agent

**Status:** Implemented

**Input:**
- Price history (Close) from the Coordinator / DataAgent
- Optional signals from other agents (event pressure from bearish Sentiment / Fundamental)

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
It runs **after** Technical, Sentiment, and Fundamental finish.

---

## 6. Coordinator Agent

**Status:** Implemented, with guardrails

**Input:**
- User ticker (checked by an **input guardrail**)
- Market data from DataAgent (checked by **tool** / **tool-output** guardrails)
- Results from Technical, Sentiment, Fundamental, and Risk agents

**Analysis:**
1. Load DataAgent **once**
2. Run Technical / Sentiment / Fundamental **in parallel** on that shared result
3. Run Risk Manager next
4. Blend live votes (+ short-horizon price context) into BUY / HOLD / SELL
5. **Decision output guardrail:** HIGH risk cannot remain a BUY

Failed specialists become `unavailable` and do not vote; the pipeline can still finish.

**Output:**
- Final recommendation: **BUY**, **HOLD**, or **SELL**
- Overall confidence score
- Short explanation
- Supporting evidence from each agent
- Guardrail event log (input / tool / output)

**Prediction horizon:** default 5 trading days (UI also offers 3 / 10)

---

## Related docs

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system diagrams
- [`PRESENTATION_AGENTS_AND_GUARDRAILS.md`](PRESENTATION_AGENTS_AND_GUARDRAILS.md) — class talk track
- [`DATA_AGENT.md`](DATA_AGENT.md) · [`TECHNICAL_AGENT.md`](TECHNICAL_AGENT.md)
