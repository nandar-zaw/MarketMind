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

**Input:**
- Price history and signals from other agents

**Future analysis:**
- Volatility
- Recent price swings
- Event risk
- Basic risk level

**Output:**
- Risk assessment / risk-adjusted view
- Confidence score
- Short explanation

---

## 6. Coordinator Agent

**Input:**
- Results from Data, Technical, Sentiment, Fundamental, and Risk agents

**Future analysis:**
- Combine all signals into one decision
- Weigh supporting and conflicting evidence
- Build a clear explanation for the user

**Output:**
- Final recommendation: **BUY**, **HOLD**, or **SELL**
- Overall confidence score
- Short explanation
- Supporting evidence from each agent

**Prediction horizon:** 5 trading days
