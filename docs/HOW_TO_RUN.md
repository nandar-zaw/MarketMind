# How to Run

Work from the **repository root** (the folder that contains `app/`, `tests/`, and `requirements.txt`).

Requirements: **Python 3.11+** (see `.python-version` if present), internet access for Yahoo Finance.

## 1. Setup (once)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then add keys
```

`.env` values (optional for a partial demo):

- `OPENAI_API_KEY` — Sentiment and Fundamental LLM agents  
- `FUNDAMENTALS_VECTOR_STORE_ID` — SEC filings vector store  

Without keys, those LLM agents report `unavailable` and the rest of the pipeline continues.

## 2. Recommended: API + dashboard together

```bash
uvicorn app.main:app --reload
```

- Dashboard: http://127.0.0.1:8000/  
- Health: http://127.0.0.1:8000/health  
- API docs: http://127.0.0.1:8000/docs  

## 3. Dashboard only

```bash
python -m app.ui
```

Open the URL printed in the terminal (usually http://127.0.0.1:7860).
The single dashboard draws its price chart as plain SVG in Gradio HTML, so
it needs no external charting library (no Plotly, no Matplotlib).

## 4. Tests

```bash
pytest
```

## 5. Disclaimer

MarketMind is an academic project. BUY / HOLD / SELL are educational model signals, **not financial advice**.
