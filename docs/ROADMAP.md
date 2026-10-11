# MarketMind Roadmap

This roadmap is for an academic AI Engineering course project.

---

## Phase 1 — done

Project structure, schemas, FastAPI health, agent scaffolding

---

## Phase 2 — done

Real stock price data + Technical Agent

- **DataAgent / market data:** OHLCV + company info via yfinance
- **Technical Agent:** RSI, SMA20/50, MACD, volume, 5-day trend

---

## Phase 3 — done

News + Sentiment Agent

- Headlines via `NewsDataService` (yfinance)
- LLM scoring grounded on those headlines when `OPENAI_API_KEY` is set
- Without the key (or with too little coverage) the agent reports
  `unavailable` and does not vote; there is no keyword fallback

---

## Phase 4 — done

Fundamental Agent

- LLM reasoning over SEC 10-K / 10-Q excerpts retrieved by
  `FilingsDataService` from the OpenAI vector store
  (`FUNDAMENTALS_VECTOR_STORE_ID`) and passed through
  `DataAgentResult.filings`
- No yfinance fundamentals snapshot; without filing evidence the agent
  reports `unavailable` and does not vote

---

## Phase 5 — done

Risk Agent

- Volatility / drawdown / risk level (low / medium / high)

---

## Phase 6 — done

Coordinator Agent

- Decision blending + input / tool / output guardrails
- Technical / Sentiment / Fundamental run **in parallel** after DataAgent

---

## Phase 7 — next

Simple ML prediction model (`app/ml/predictor.py` still a placeholder)

---

## Phase 8 — next

Simple backtesting

---

## Phase 9 — done

Dashboard

- Single Gradio UI (`app/ui.py`), also mounted by `app/main.py` at `/`
  (`python -m app.ui` or `uvicorn app.main:app`)
- Price chart drawn as hand-built SVG inside Gradio, with no external
  charting library
- Ticker selector, horizon control, FastAPI `/analyze/{ticker}`

---

## Phase 10 — in progress

Final testing and presentation

- See [`PRESENTATION_AGENTS_AND_GUARDRAILS.md`](PRESENTATION_AGENTS_AND_GUARDRAILS.md)
- Overview / run guide / code map: [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md), [`HOW_TO_RUN.md`](HOW_TO_RUN.md), [`CODE_MAP.md`](CODE_MAP.md)
