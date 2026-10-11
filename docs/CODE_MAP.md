# Code Map

Paths are relative to the **repository root**.

## Entry points

| Path | Role |
| --- | --- |
| `app/main.py` | FastAPI: `/health`, `/analyze/{ticker}`, Gradio mounted at `/` |
| `app/ui.py` | Gradio dashboard (Plotly charts) |
| `app/ui_gradio_only.py` | Gradio dashboard (SVG charts, no Plotly) |

## Agents

| Path | Role |
| --- | --- |
| `app/agents/coordinator_agent.py` | Orchestrator; parallel specialists; final blend |
| `app/agents/data_agent.py` | Shared data fetch (prices, news, filings) |
| `app/agents/technical_agent.py` | RSI / SMA / MACD votes |
| `app/agents/sentiment_agent.py` | News sentiment (LLM) |
| `app/agents/fundamental_agent.py` | SEC filing excerpts (LLM) |
| `app/agents/risk_agent.py` | Volatility / drawdown → low/medium/high |
| `app/agents/base_agent.py` | Shared agent interface |

## Guardrails & schemas

| Path | Role |
| --- | --- |
| `app/guardrails.py` | Input / tool / output / decision guardrails |
| `app/models/schemas.py` | Pydantic models (`FinalRecommendation`, etc.) |

## Data services

| Path | Role |
| --- | --- |
| `app/services/market_data.py` | yfinance OHLCV + company info |
| `app/services/news_data.py` | yfinance news headlines |
| `app/services/filings_data.py` | SEC filing excerpts (vector store) |

## Helpers

| Path | Role |
| --- | --- |
| `app/utils/helpers.py` | `normalize_ticker` (incl. S&P aliases → SPY) |
| `app/utils/symbols.py` | `SPY` / alias constants |

## Tests (representative)

| Path | Role |
| --- | --- |
| `tests/test_agents.py` | Coordinator / guardrail behavior |
| `tests/test_data_agent.py` | DataAgent (mocked) |
| `tests/test_guardrails.py` | Guardrail rules |
| `tests/test_symbols.py` | Alias resolution |

## Parallel specialists (talking point)

In `app/agents/coordinator_agent.py`, method `_collect_specialists` uses `asyncio.gather` so Technical, Sentiment, and Fundamental run together on the shared `DataAgentResult`. Risk runs afterward.
