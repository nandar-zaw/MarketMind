# MarketMind — Professor Submission Package

**Course:** CS529 Artificial Intelligence / AI Engineering  
**Project:** MarketMind — Multi-Agent Market Trend Signals  
**This folder is a complete, runnable copy of the project.**

> **Disclaimer:** Educational course project only. Outputs are **not financial advice**.

---

## Quick start (on the professor’s machine)

Open a terminal **inside this `submission` folder** (the folder that contains `app/` and `requirements.txt`):

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# Main UI (Plotly charts)
python -m app.ui

# OR Gradio-only UI (SVG charts, no Plotly)
python -m app.ui_gradio_only
```

Then open the URL printed in the terminal (usually http://127.0.0.1:7860).

**Optional API:**

```bash
uvicorn app.main:app --reload
# http://127.0.0.1:8000/analyze/SPY
# http://127.0.0.1:8000/docs
```

**Optional OpenAI key** (LLM sentiment): copy `.env.example` → `.env` and set `OPENAI_API_KEY`.  
Without a key, Sentiment still works with a keyword fallback.

**Tests:**

```bash
pytest
```

Detailed steps: [`02_HOW_TO_RUN.md`](02_HOW_TO_RUN.md).

---

## Package contents

| Item | Purpose |
| --- | --- |
| `app/` | Full source (agents, services, FastAPI, both Gradio UIs) |
| `tests/` | Unit tests |
| `docs/` | Project documentation |
| `requirements.txt` | Python dependencies |
| `.env.example` | Optional env template (no secrets included) |
| `PROJECT_README.md` | Full project README |
| `01_` … `07_` | Grading / presentation guides (below) |

---

## Grading / presentation guides

| Order | File | Purpose |
| ---: | --- | --- |
| 1 | [`01_PROJECT_OVERVIEW.md`](01_PROJECT_OVERVIEW.md) | One-page summary |
| 2 | [`02_HOW_TO_RUN.md`](02_HOW_TO_RUN.md) | Install + demo |
| 3 | [`03_PRESENTATION_AGENTS_AND_GUARDRAILS.md`](03_PRESENTATION_AGENTS_AND_GUARDRAILS.md) | Talk track |
| 4 | [`04_ARCHITECTURE.md`](04_ARCHITECTURE.md) | Architecture |
| 5 | [`05_AGENTS.md`](05_AGENTS.md) | Agent details |
| 6 | [`06_ROADMAP.md`](06_ROADMAP.md) | Phase status |
| 7 | [`07_CODE_MAP.md`](07_CODE_MAP.md) | Source file map |

---

## What is implemented

- Multi-agent pipeline: Data → Technical / Sentiment / Fundamental (**parallel**) → Risk → Coordinator  
- Input / tool / output guardrails  
- Yahoo Finance via yfinance (prices, fundamentals, news)  
- FastAPI + two Gradio UIs  
- Structured BUY / HOLD / SELL with explanations  

## Not complete (stated clearly)

- Phase 7 ML model (placeholder)  
- Phase 8 backtesting  

---

## Upstream repository (optional)

https://github.com/nandar-zaw/MarketMind · branch `Dev_1009`  

You do **not** need GitHub if you have this folder — it is executable by itself.
