# Data Collector Agent (DataAgent)

This document explains the **Data Collector Agent** of MarketMind: what it does,
how it is wired, and how to use it. It is written to be easy to explain in class.

The DataAgent **gathers and prepares market data**. It does **not** calculate
indicators, score sentiment, score fundamentals, score risk, or make
BUY/HOLD/SELL decisions. Those belong to the specialist agents and the
Coordinator.

---

## 1. Purpose

Given a market symbol (the examples below use `AAPL`, which has SEC filings in the store), the DataAgent:

- downloads historical OHLCV prices (Open, High, Low, Close, Volume)
- collects basic company / fund information
- retrieves **SEC filing evidence** (10-K / 10-Q excerpts) from the project's
  OpenAI vector store via `FilingsDataService`
- fetches recent **news headlines** (`NewsDataService` / yfinance)
- validates, cleans, and degrades gracefully on partial failures
- returns structured Pydantic models for the other agents

Default lookback is approximately **one year**.

---

## 2. Data flow

```text
User / Coordinator
        |
        v
   DataAgent (async analyze)
        |
        +--> MarketDataService  --> yfinance   (prices + company info)
        |
        +--> NewsDataService    --> yfinance   (headlines)
        |
        +--> FilingsDataService --> OpenAI vector store (SEC filing excerpts)
```

Why this shape:

- **DataAgent** owns the "collect data and return a structured result" job.
- The services isolate external provider calls, so yfinance / the vector store
  can be replaced later without touching the agent.
- This keeps the agent small and the providers swappable.
- The Coordinator loads DataAgent **once**, then shares the result with
  Technical, Sentiment, and Fundamental (in parallel).
- The Fundamental Agent never calls the vector store itself: it receives the
  excerpts through `DataAgentResult.filings` (RAG data supply lives in the
  data layer).

---

## 3. Files involved

| File | Responsibility |
| --- | --- |
| `app/agents/data_agent.py` | `DataAgent` — the agent entry point (`analyze`) |
| `app/services/market_data.py` | `MarketDataService` — prices + Yahoo `.info` |
| `app/services/news_data.py` | `NewsDataService` — headlines via yfinance |
| `app/services/filings_data.py` | `FilingsDataService` — SEC filing excerpts (OpenAI vector store) |
| `app/models/schemas.py` | `MarketPrice`, `CompanyInfo`, `NewsItem`, `FilingExcerpt`, `DataAgentResult` |
| `app/utils/exceptions.py` | `MarketDataError` |
| `app/utils/helpers.py` | `normalize_ticker` (uppercase + trim) |
| `tests/test_data_agent.py`, `tests/test_filings_data.py` | Mocked unit tests (no network needed) |

---

## 4. Structured models

### MarketPrice

One daily OHLCV observation.

- `date`, `open`, `high`, `low`, `close`, `volume`
- `adj_close` (optional; included when the provider returns it)

### CompanyInfo

Basic company / fund metadata. Missing fields are `None` instead of crashing.

- `ticker`, `company_name`, `sector`, `industry`, `exchange`, `currency`, `market_cap`

### NewsItem

One recent headline for the Sentiment Agent.

- `title`, `publisher`, `published`, `summary`

### FilingExcerpt

One retrieved passage from a company's SEC filings (10-K / 10-Q).

- `text` — the retrieved passage
- `source` — filing file name when known (e.g. `AAPL_10-K.txt`)
- `score` — retrieval relevance score when provided

### DataAgentResult

The DataAgent output.

- `ticker`
- `company_info`
- `price_history` (oldest to newest)
- `news` (`list[NewsItem]`)
- `filings` (`list[FilingExcerpt]`) — the Fundamental Agent's RAG input
- `start_date`, `end_date`
- `records_count`

> There is **no** `fundamentals` field. Earlier drafts used a yfinance
> `FundamentalSnapshot`; the current design instead gives the Fundamental Agent
> SEC filing excerpts and lets an LLM reason over them.

---

## 5. Usage

```python
import asyncio

from app.agents.data_agent import DataAgent

result = asyncio.run(DataAgent().analyze("AAPL"))

print(result.ticker)              # AAPL
print(result.company_info.company_name)
print(result.records_count)       # number of OHLCV rows
print(result.price_history[0])    # first (oldest) bar
print(result.price_history[-1])   # last (newest) bar
print(len(result.news))           # recent headlines for Sentiment
print(len(result.filings))        # SEC filing excerpts for Fundamental
print(result.filings[0].source)   # source file name, when known
```

> The Fundamental Agent reads `result.filings`. When the vector store is not
> configured, `result.filings` is empty and that agent reports `unavailable`.

> **Why `AAPL` here?** MarketMind's default demo symbol is `SPY`, but `SPY` is an
> ETF with no 10-K/10-Q in the store, so `filings` would be empty. `AAPL` is used
> in these examples so the filing-evidence output is actually illustrated.

### Arguments

`DataAgent.analyze(ticker, *, start=None, end=None, period="1y", as_of_date=None)`

- `ticker` — required; normalized to uppercase (`aapl` -> `AAPL`)
- `start` / `end` — optional dates in `YYYY-MM-DD`
- `period` — yfinance period used when `start`/`end` are omitted (default `1y`)
- `as_of_date` — optional cutoff date, see below

---

## 6. Configuration

| Env var | Purpose |
| --- | --- |
| `FUNDAMENTALS_VECTOR_STORE_ID` | OpenAI vector store holding the SEC filings. Unset → no filing evidence (empty `filings`). |
| `OPENAI_API_KEY` | Used by the retrieval client and the LLM agents. |

Filings are cached in-process for 30 minutes (like news): filing text does not
change minute to minute, so repeated analyses skip the retrieval call.

---

## 7. Future-data protection (`as_of_date`)

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

## 8. Data cleaning

The service:

- sorts observations chronologically (oldest first)
- drops rows missing critical OHLCV values
- raises a clear error if nothing usable remains

It does **not** compute RSI, MACD, SMA, EMA, Bollinger Bands, or any signals.

---

## 9. Error handling

Expected failures raise a single, clear exception: `MarketDataError`.

Examples:

- empty or whitespace-only ticker
- no historical data returned for the ticker
- malformed dates (must be `YYYY-MM-DD`)
- provider / network failure

**Prices are required; news and filings are supporting data.** If the news
provider or the vector store fails, the DataAgent logs a warning and continues
with an empty list rather than failing the whole run. Provider errors for prices
are wrapped into `MarketDataError` with a short message.

---

## 10. Logging

The service logs useful, small events:

- ticker requested, and the date range / period
- number of records retrieved
- how many filing excerpts were fetched (or that the store is unset)
- provider failures

It does **not** log full DataFrames or environment details.

---

## 11. Async note

`yfinance` is a synchronous library, and the vector-store client is too.
`DataAgent.analyze` stays `async` to match the shared `BaseAgent` interface,
but it calls the synchronous services directly (blocking). This is intentional
and simple: we do not pretend the calls are truly asynchronous. If the app later
needs to avoid blocking the event loop, that can be handled in one place
(for example a thread executor) without changing the agent interface.

---

## 12. Tests

`tests/test_data_agent.py` covers, using mocked provider responses (no network):

1. lowercase ticker becomes uppercase
2. empty ticker is rejected
3. historical data is mapped correctly to `MarketPrice`
4. company metadata is mapped correctly to `CompanyInfo`
5. empty provider response is handled
6. `as_of_date` prevents future observations
7. `DataAgent` returns the expected Pydantic structure
8. news / filings failures degrade to empty lists instead of raising

`tests/test_filings_data.py` covers the vector-store retrieval path.

Run:

```bash
pytest tests/test_data_agent.py tests/test_filings_data.py
```

---

## 13. Out of scope

The DataAgent does **not** implement:

- technical indicators (RSI, SMA, MACD, ...) or trading signals
- sentiment analysis or scoring
- fundamental scoring (it only supplies filing evidence the LLM reasons over)
- risk scoring
- ML predictions
- BUY / HOLD / SELL recommendations
- Coordinator decision logic
- backtesting engine or dashboard

DataAgent gathers and prepares data only.
