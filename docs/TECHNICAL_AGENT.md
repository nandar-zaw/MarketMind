# Technical Analysis Agent (TechnicalAgent)

This document explains the **Technical Analysis Agent** of MarketMind: what it
does, how it uses DataAgent output, and how the signal is calculated. It is
written to be easy to explain in class.

The TechnicalAgent **analyzes price history**. It does **not** download market
data, run sentiment/fundamentals, score risk, or make BUY/HOLD/SELL decisions.
Those belong to DataAgent, other specialists, Risk, and the Coordinator.

---

## 1. Purpose

Given historical OHLCV data (usually from DataAgent), the TechnicalAgent:

- calculates RSI(14), SMA20, SMA50, and MACD (12/26/9)
- checks a simple 5-trading-day price trend
- notes volume vs its 20-day average (supporting evidence only)
- combines the indicator votes into **bullish / neutral / bearish**
- returns a confidence score and a short human-readable explanation

Course demos often use **`SPY`** as an S&P 500 proxy. The agent itself works
with whatever OHLCV series DataAgent provides.

---

## 2. Data flow

```text
DataAgent.analyze(ticker)
        |
        | DataAgentResult.price_history  (list[MarketPrice])
        v
TechnicalAgent.analyze_prices(...)
        |
        | RSI, SMA20/50, MACD, volume, 5-day trend
        v
TechnicalAnalysisResult  (detailed)
        |
        v
AgentResult  (signal / confidence / explanation)
        |
        v
   Coordinator (later / already wired)
```

Why this shape:

- **DataAgent** owns collecting data.
- **TechnicalAgent** owns analyzing that data.
- TechnicalAgent never calls yfinance directly. If only a ticker is passed to
  `analyze()`, it asks DataAgent for the OHLCV first.

---

## 3. Files involved

| File | Responsibility |
| --- | --- |
| `app/agents/technical_agent.py` | `TechnicalAgent` — indicators, scoring, explanation |
| `app/agents/data_agent.py` | Supplies OHLCV when `data=` is not passed in |
| `app/models/schemas.py` | `MarketPrice`, `DataAgentResult`, `TechnicalAnalysisResult`, `AgentResult` |
| `tests/test_technical_agent.py` | Synthetic unit tests (no network) |

---

## 4. Structured models

### TechnicalAnalysisResult

Detailed technical output:

- `signal` — `bullish` | `neutral` | `bearish`
- `confidence` — 0.0 – 1.0
- `rsi`, `sma20`, `sma50`, `macd`, `macd_signal`
- `price_change_5d` — fraction (e.g. `0.012` = +1.2%)
- `volume_trend` — `above_average` | `normal` | `below_average` | `unavailable`
- `explanation` — short text built from the indicator values
- `score` — sum of indicator votes (for transparency)

### AgentResult

What the Coordinator expects from specialists:

- `agent_name` = `technical_agent`
- `signal` = `bullish` | `neutral` | `bearish` (**never** BUY/HOLD/SELL)
- `confidence`
- `explanation`

---

## 5. Usage

```python
import asyncio

from app.agents.data_agent import DataAgent
from app.agents.technical_agent import TechnicalAgent

async def main():
    data = await DataAgent().analyze("SPY")
    tech = TechnicalAgent()

    # Detailed result (good for demos / debugging)
    detail = tech.analyze_prices(data.price_history)
    print(detail.signal, detail.confidence, detail.score)
    print(detail.explanation)

    # Coordinator-compatible result
    result = await tech.analyze("SPY", data=data)
    print(result.signal, result.confidence)

asyncio.run(main())
```

If you omit `data=`, TechnicalAgent asks DataAgent for you:

```python
result = asyncio.run(TechnicalAgent().analyze("SPY"))
```

### Minimum data

TechnicalAgent needs at least **50** trading days (for SMA50). With fewer bars
it raises:

```text
ValueError: Not enough historical data for technical analysis.
```

---

## 6. Indicators (beginner view)

### RSI(14)

Measures how strong recent up-moves are versus down-moves.

- RSI > 70 → potentially overbought → bearish vote (−1)
- RSI < 30 → potentially oversold → bullish vote (+1)
- otherwise → neutral (0)

### SMA20 vs SMA50

Compares a short average to a medium average.

- SMA20 clearly above SMA50 → bullish (+1)
- SMA20 clearly below SMA50 → bearish (−1)
- roughly equal → neutral (0)

### MACD (12 / 26 / 9)

`MACD = EMA12 − EMA26`, then a 9-period EMA signal line.

- MACD clearly above signal → bullish (+1)
- MACD clearly below signal → bearish (−1)
- roughly equal → neutral (0)

### 5-day price trend

Compares the latest close to the close 5 trading days earlier
(matches the project’s 5-day horizon).

- rise > 0.5% → bullish (+1)
- fall > 0.5% → bearish (−1)
- small move → neutral (0)

### Volume trend (supporting only)

Compares the latest volume to its 20-day average:

- `above_average` / `normal` / `below_average` / `unavailable`

Volume is mentioned in the explanation. It does **not** add to the numeric score.

---

## 7. Signal calculation

Each of RSI, SMA, MACD, and 5-day trend votes **+1 / 0 / −1**.

```text
score = rsi_vote + sma_vote + macd_vote + price_vote

score >= +2  →  bullish
score <= -2  →  bearish
otherwise    →  neutral
```

Example:

```text
RSI                  0
SMA20 > SMA50       +1
MACD > Signal       +1
5-day trend         +1
--------------------
Total               +3  →  bullish
```

---

## 8. Confidence calculation

Confidence is transparent (no fake AI probability):

```text
confidence = min(0.95, 0.45 + 0.125 * |score| + 0.05 * agreement_bonus)
```

`agreement_bonus` = how many non-zero votes share the same sign as `score`
(0 when score is 0).

Strong agreement → higher confidence. Conflicting votes → lower confidence.

---

## 9. Explanation

Built with normal Python f-strings from the computed values. No LLM.

Example:

```text
The technical outlook is bullish (score=+3). RSI(14) is 67.2 (neutral).
SMA20 (764.30) is above SMA50 (762.98). MACD (1.9732) is above its
signal (1.4730). Price rose 1.2% over the last 5 trading days.
Volume is below average.
```

---

## 10. Tests

`tests/test_technical_agent.py` uses synthetic rising / falling / flat price
series (no network):

1. RSI is in a valid range
2. SMA20 and SMA50 are calculated
3. MACD and signal line are calculated
4. 5-day price change is calculated
5. Rising data → bullish
6. Falling data → bearish
7. Flat data → neutral
8. Fewer than 50 bars → clear error

Run:

```bash
pytest tests/test_technical_agent.py
```

---

## 11. Out of scope

TechnicalAgent does **not** implement:

- market data download (DataAgent’s job)
- sentiment, fundamentals, or risk scoring
- ML or LLM explanations
- BUY / HOLD / SELL recommendations
- Coordinator decision logic
- backtesting or dashboard

It provides one piece of evidence: a technical market signal.

---

## 12. Short presentation script

> TechnicalAgent does not download prices. It takes DataAgent’s OHLCV bars,
> computes RSI, SMA20/50, MACD, and a 5-day price change with pandas, lets each
> indicator vote +1, 0, or −1, sums those votes into a score, and maps the score
> to bullish, neutral, or bearish. Confidence rises when the score is strong and
> the votes agree. Volume is only mentioned in the explanation. The agent never
> outputs BUY, HOLD, or SELL — that stays with the Coordinator.
