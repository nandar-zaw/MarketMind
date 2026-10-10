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
- LLM scoring when `OPENAI_API_KEY` is set; keyword fallback otherwise

---

## Phase 4 — done

Fundamental Agent

- Scores `FundamentalSnapshot` from DataAgent (yfinance `.info`)
- No SEC file storage required

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

- Gradio UI with Plotly charts (`python -m app.ui`)
- Alternate Gradio-only SVG UI (`python -m app.ui_gradio_only`)
- Ticker selector, horizon control, FastAPI `/analyze/{ticker}`

---

## Phase 10 — in progress

Final testing and presentation

- See [`PRESENTATION_AGENTS_AND_GUARDRAILS.md`](PRESENTATION_AGENTS_AND_GUARDRAILS.md)
- Professor hand-in package: [`../submission/`](../submission/)
