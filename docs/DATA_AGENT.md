# Data Collector Agent (DataAgent)

This document explains the **Data Collector Agent** of MarketMind: what it does,
how it is wired, and how to use it. It is written to be easy to explain in class.

The DataAgent **gathers and prepares market data**. It does **not** calculate
indicators, run sentiment/fundamentals, score risk, or make BUY/HOLD/SELL
decisions. Those belong to later agents and phases.

---

## 1. Purpose

Given a market symbol such as `SPY` (S&P 500 ETF proxy), the DataAgent:

- downloads historical OHLCV prices (Open, High, Low, Close, Volume)
- collects basic company information (name, sector, industry, exchange, currency, market cap)
- validates and cleans the data
- returns it as structured Pydantic models for the other agents

Default lookback is approximately **one year**.

---

## 2. Data flow

```text
User / Coordinator
        |
        v
   DataAgent (async analyze)
        |
        v
 MarketDataService  (synchronous)
        |
        v
     yfinance
```

Why this shape:

- **DataAgent** owns the "collect data and return a structured result" job.
- **MarketDataService** isolates all external provider calls, so yfinance can be
  replaced later without touching the agent.
- This keeps the agent small and the provider swappable.

---

## 3. Files involved

| File | Responsibility |
| --- | --- |
| `app/agents/data_agent.py` | `DataAgent` — the agent entry point (`analyze`) |
| `app/services/market_data.py` | `MarketDataService` — talks to yfinance |
| `app/models/schemas.py` | `MarketPrice`, `CompanyInfo`, `DataAgentResult` |
| `app/utils/exceptions.py` | `MarketDataError` |
| `app/utils/helpers.py` | `normalize_ticker` (uppercase + trim) |
| `tests/test_data_agent.py` | Mocked unit tests (no network needed) |

---

## 4. Structured models

### MarketPrice

One daily OHLCV observation.

- `date`, `open`, `high`, `low`, `close`, `volume`
- `adj_close` (optional; included when the provider returns it)

### CompanyInfo

Basic company / fund metadata. Missing fields are `None` instead of crashing.

- `ticker`, `company_name`, `sector`, `industry`, `exchange`, `currency`, `market_cap`

### FundamentalSnapshot

Fundamental metrics from a **direct yfinance API call** (not SEC file storage).

Typical fields:

- Valuation: `trailing_pe`, `forward_pe`, `price_to_book`, `price_to_sales`, `dividend_yield`
- Quality / growth: `profit_margins`, `operating_margins`, `revenue_growth`, `earnings_growth`, `return_on_equity`
- Balance sheet: `debt_to_equity`, `total_cash`, `total_debt`
- Market: `beta`, `fifty_two_week_high`, `fifty_two_week_low`
- ETF-friendly: `quote_type`, `total_assets`, `ytd_return`, `three_year_avg_return`

For `SPY`, company income-statement fields are often `None`; ETF fields are filled when Yahoo provides them.

### DataAgentResult

The DataAgent output.

- `ticker`
- `company_info`
- `fundamentals` (`FundamentalSnapshot` from the market API)
- `price_history` (oldest to newest)
- `news`
- `start_date`, `end_date`
- `records_count`

---

## 5. Usage

```python
import asyncio

from app.agents.data_agent import DataAgent

result = asyncio.run(DataAgent().analyze("SPY"))

print(result.ticker)              # SPY
print(result.company_info.company_name)
print(result.fundamentals.trailing_pe)
print(result.fundamentals.quote_type)  # often ETF
print(result.records_count)       # number of OHLCV rows
print(result.price_history[0])    # first (oldest) bar
print(result.price_history[-1])   # last (newest) bar
print(len(result.news))           # recent headlines for Sentiment
```

> Fundamental Agent teammates should read `result.fundamentals` instead of
> OpenAI file-storage / SEC RAG for the S&P 500 path.


### Arguments

`DataAgent.analyze(ticker, *, start=None, end=None, period="1y", as_of_date=None)`

- `ticker` — required; normalized to uppercase (`aapl` -> `AAPL`)
- `start` / `end` — optional dates in `YYYY-MM-DD`
- `period` — yfinance period used when `start`/`end` are omitted (default `1y`)
- `as_of_date` — optional cutoff date, see below

---

## 6. Future-data protection (`as_of_date`)

MarketMind will later evaluate the system on historical data. To avoid leaking
future information, you can pass an `as_of_date`:

```python
result = asyncio.run(DataAgent().analyze("AAPL", as_of_date="2025-01-15"))
```

When set, the DataAgent **must not return any price observation after that date**.
This is done in two layers:

1. the fetch end is clamped to `as_of_date`
2. after mapping, any row dated after `as_of_date` is skipped

This is a guard against look-ahead bias. It is **not** a backtesting engine —
that is a later phase.

---

## 7. Data cleaning

The service:

- sorts observations chronologically (oldest first)
- drops rows missing critical OHLCV values
- raises a clear error if nothing usable remains

It does **not** compute RSI, MACD, SMA, EMA, Bollinger Bands, or any signals.

---

## 8. Error handling

Expected failures raise a single, clear exception: `MarketDataError`.

Examples:

- empty or whitespace-only ticker
- no historical data returned for the ticker
- malformed dates (must be `YYYY-MM-DD`)
- provider / network failure

Raw library stack traces are not the normal API surface; provider errors are
wrapped into `MarketDataError` with a short message.

---

## 9. Logging

The service logs useful, small events:

- ticker requested, and the date range / period
- number of records retrieved
- provider failures

It does **not** log full DataFrames or environment details.

---

## 10. Async note

`yfinance` is a synchronous library. `DataAgent.analyze` stays `async` to match
the shared `BaseAgent` interface, but it calls the synchronous service directly
(blocking). This is intentional and simple: we do not pretend the calls are
truly asynchronous. If the app later needs to avoid blocking the event loop,
that can be handled in one place (for example a thread executor) without
changing the agent interface.

---

## 11. Tests

`tests/test_data_agent.py` covers, using mocked provider responses (no network):

1. lowercase ticker becomes uppercase
2. empty ticker is rejected
3. historical data is mapped correctly to `MarketPrice`
4. company metadata is mapped correctly to `CompanyInfo`
5. empty provider response is handled
6. `as_of_date` prevents future observations
7. `DataAgent` returns the expected Pydantic structure

Run:

```bash
pytest tests/test_data_agent.py
```

---

## 12. Out of scope

The DataAgent does **not** implement:

- technical indicators (RSI, SMA, MACD, ...) or trading signals
- sentiment analysis or news APIs
- fundamental scoring
- risk scoring
- ML predictions or LLM calls
- BUY / HOLD / SELL recommendations
- Coordinator decision logic
- backtesting engine or dashboard

DataAgent gathers and prepares data only.
