# MarketMind — Course Submission Package

**Course:** CS529 Artificial Intelligence / AI Engineering  
**Project:** MarketMind — Multi-Agent System for Market Trend Signals  
**Branch:** `Dev_1009`  
**Repository:** https://github.com/nandar-zaw/MarketMind  

> **Disclaimer:** Educational course project only. Outputs are **not financial advice**.

---

## What to open first

| Order | File | Purpose |
| ---: | --- | --- |
| 1 | [`01_PROJECT_OVERVIEW.md`](01_PROJECT_OVERVIEW.md) | One-page summary for grading |
| 2 | [`02_HOW_TO_RUN.md`](02_HOW_TO_RUN.md) | Install + launch demo (two UIs) |
| 3 | [`03_PRESENTATION_AGENTS_AND_GUARDRAILS.md`](03_PRESENTATION_AGENTS_AND_GUARDRAILS.md) | Talk track + diagrams |
| 4 | [`04_ARCHITECTURE.md`](04_ARCHITECTURE.md) | System architecture |
| 5 | [`05_AGENTS.md`](05_AGENTS.md) | Per-agent roles and I/O |
| 6 | [`06_ROADMAP.md`](06_ROADMAP.md) | Phase checklist / status |
| 7 | [`07_CODE_MAP.md`](07_CODE_MAP.md) | Where to find key code |

Full project docs also live under [`../docs/`](../docs/).  
Root setup notes: [`../README.md`](../README.md).

---

## Demo in 60 seconds

```bash
# from repo root
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Main UI (Plotly charts)
python -m app.ui

# OR Gradio-only UI (SVG charts, no Plotly)
python -m app.ui_gradio_only
```

Open the printed URL (usually http://127.0.0.1:7860) → pick **SPY** → **Run analysis**.

API alternative: `uvicorn app.main:app --reload` → http://127.0.0.1:8000/analyze/SPY

---

## Delivered features

- Multi-agent pipeline: Data → Technical / Sentiment / Fundamental (**parallel**) → Risk → Coordinator
- Input / tool / output **guardrails**
- Yahoo Finance data via **yfinance** (prices, fundamentals, news)
- FastAPI + two Gradio dashboards (Plotly and SVG-only)
- Structured BUY / HOLD / SELL recommendation with explanations

## Not claimed as complete

- Phase 7 ML prediction model (placeholder)
- Phase 8 backtesting
