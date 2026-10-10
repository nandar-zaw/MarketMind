# 07 — Code Map (where to look during code review)

Paths are relative to the repository root.

## Entry points

| Path | Role |
| --- | --- |
| `app/main.py` | FastAPI: `/health`, `/analyze/{ticker}` |
| `app/ui.py` | Gradio dashboard (Plotly charts) |
| `app/ui_gradio_only.py` | Gradio dashboard (SVG charts, no Plotly) |

## Agents

| Path | Role |
| --- | --- |
| `app/agents/coordinator_agent.py` | Orchestrator; parallel specialists; final blend |
| `app/agents/data_agent.py` | Shared data fetch (prices, fundamentals, news) |
| `app/agents/technical_agent.py` | RSI / SMA / MACD votes |
| `app/agents/sentiment_agent.py` | News sentiment (LLM or keyword) |
| `app/agents/fundamental_agent.py` | Scores `FundamentalSnapshot` |
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
| `app/services/market_data.py` | yfinance OHLCV + `.info` fundamentals |
| `app/services/news_data.py` | yfinance news headlines |

## Symbol helpers

| Path | Role |
| --- | --- |
| `app/utils/symbols.py` | `SPY` default + aliases (`^GSPC`, `SP`, …) |
| `app/utils/helpers.py` | `normalize_ticker` |

## Tests (representative)

| Path | Role |
| --- | --- |
| `tests/test_agents.py` | Coordinator / guardrail behavior |
| `tests/test_data_agent.py` | DataAgent (mocked) |
| `tests/test_ui_chart.py` | Chart helpers |
| `tests/test_symbols.py` | Alias resolution |

## Parallel specialists (talking point)

In `app/agents/coordinator_agent.py`, method `_collect_specialists` uses `asyncio.gather` so Technical, Sentiment, and Fundamental run together on the shared `DataAgentResult`. Risk runs afterward.
