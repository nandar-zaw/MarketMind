# 02 — How to Run (for the professor)

Requirements: **Python 3.12+**, internet access for Yahoo Finance (yfinance).

## 1. Setup (once)

From the **repository root** (parent of `submission/`):

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

On Windows, if `python` is missing: `py -3.12 -m venv .venv`.

Optional: copy `.env.example` → `.env` and set `OPENAI_API_KEY` for LLM sentiment.
Without a key, Sentiment still runs with a **keyword fallback**.

## 2. Gradio UI (recommended demo)

### Main UI — Plotly charts

```bash
python -m app.ui
```

### Alternate UI — Gradio-only SVG charts (no Plotly)

```bash
python -m app.ui_gradio_only
```

Open the URL printed in the terminal (usually http://127.0.0.1:7860).

**Demo steps:**

1. Ticker defaults to `SPY` (or pick QQQ, NVDA, AAPL, … / type a symbol).  
2. Choose horizon (3 / 5 / 10 trading days).  
3. Click **Run analysis**.  
4. Inspect: quote, chart windows (1D–1Y), BUY/HOLD/SELL, agent pipeline, headlines, specialist reports.

## 3. FastAPI (optional)

```bash
uvicorn app.main:app --reload
```

| URL | Purpose |
| --- | --- |
| http://127.0.0.1:8000/health | Health check |
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/analyze/SPY | Full analysis JSON |
| http://127.0.0.1:8000/analyze/not-a-ticker | Input guardrail demo (400) |

You do **not** need FastAPI running at the same time as Gradio — the UI calls agents in-process.

## 4. Tests

```bash
pytest
```

## 5. Troubleshooting

| Issue | Fix |
| --- | --- |
| Empty chart / no prices | Check internet; Yahoo may rate-limit — retry |
| Sentiment “Keyword” chip | Set `OPENAI_API_KEY` in `.env` and restart UI |
| Port busy | Gradio may open 7861+; use the URL in the terminal |
| Bad ticker | Input guardrail rejects invalid symbols |

## 6. Disclaimer (must mention in demo)

MarketMind is an academic project. BUY / HOLD / SELL are educational model signals, **not financial advice**.
