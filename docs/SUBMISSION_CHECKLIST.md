# Submission Checklist

A short, ordered checklist to run before handing the project in, so the
professor can run it safely on their own machine.

---

## 1. Never ship secrets

- [ ] `.env` is **not** in the archive. It is already in `.gitignore`; confirm with `git status` that it does not appear.
- [ ] `.venv/` (or any virtualenv) is **not** in the archive. It is gitignored; do not zip a working directory that contains it.
- [ ] `.env.example` (placeholders only) **is** included, so the professor knows which keys to set.
- [ ] `__pycache__/`, `.pytest_cache/`, and `*.pyc` are excluded.

Quick check (PowerShell), run from the repository root:

```powershell
git status --porcelain          # .env / .venv must NOT appear
git ls-files | Select-String "\.env$"   # expected: no output
```

## 2. Rotate any key that may have been shared

If `OPENAI_API_KEY` was ever pasted into a chat, a screenshot, or a zip:

- [ ] Rotate it in the OpenAI dashboard and update your local `.env`.
- [ ] Confirm the old key no longer works.

> The project calls OpenAI at runtime (Sentiment + Fundamental agents and the
> SEC filing vector store). A leaked key can spend real quota.

## 3. Fresh-machine install

- [ ] Python 3.11+ is installed.
- [ ] Create a clean environment and install pinned dependencies:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] Copy `.env.example` to `.env` and set `OPENAI_API_KEY` and `FUNDAMENTALS_VECTOR_STORE_ID`.
- [ ] Without keys, the app still runs: the LLM agents report `unavailable` and the pipeline continues with Technical + Risk.

## 4. Tests are green

- [ ] Run the full suite (no network, no real model calls needed):

```bash
pytest
```

- [ ] Expected: **all tests pass** (the suite includes agent, service, guardrail, UI, and API-guard tests).

## 5. Both UIs launch and analyze

Run each command, then open the printed URL and click **Analyze** (the page
opens as an idle shell; nothing hits the network until you click):

```bash
# Mounted production UI (Gradio LinePlot charts)
uvicorn app.main:app --reload      # dashboard at http://127.0.0.1:8000/
python -m app.ui                   # or standalone at http://127.0.0.1:7860

# Gradio-only UI (hand-built SVG charts, no Plotly / Matplotlib)
python -m app.ui_gradio_only
```

- [ ] Each UI returns a BUY / HOLD / SELL recommendation with a confidence score, per-agent panels, and a price chart.
- [ ] Changing the chart window (3M / 6M / 1Y) re-filters instantly without a new analysis.
- [ ] Default ticker is `AAPL`; `MSFT`, `NVDA`, `TSLA`, `AMZN` have SEC filings in the store.

## 6. Guardrails and API behave as documented

- [ ] Bad input is rejected (HTTP 400):

```bash
curl http://127.0.0.1:8000/analyze/not-a-ticker
```

- [ ] A normal request returns a structured recommendation:

```bash
curl -X POST "http://127.0.0.1:8000/analyze/NVDA?horizon_days=10"
```

- [ ] The public `/analyze` endpoint is rate-limited per client IP by default
  (`ANALYZE_RATE_LIMIT=30` / `ANALYZE_RATE_WINDOW_SECONDS=60`; set the limit to
  `0` to disable). Set `DEMO_API_TOKEN` to additionally require an
  `X-Demo-Token` header. `APP_ENV=production` hides `/docs`.

## 7. Demo day (quick script)

1. `uvicorn app.main:app --reload` → open http://127.0.0.1:8000/.
2. Click **Analyze** on the default `AAPL`.
3. Walk through: DataAgent → parallel Technical / Sentiment / Fundamental → Risk → Coordinator blend → output guardrail.
4. Show the guardrail audit trail at the bottom of the final panel.
5. Switch the ticker (e.g. `NVDA`) and the horizon, and re-run.
6. Optionally show `python -m app.ui_gradio_only` as the "no chart library beyond Gradio" variant.

## 8. Known limits (be upfront in the demo)

- Fundamental analysis only has SEC filings for **AAPL, MSFT, NVDA, TSLA, AMZN**; other tickers report `unavailable` for that agent.
- The ML predictor (`app/ml/`) is a placeholder and is **not** part of the current decision.
- Yahoo Finance data may be delayed or briefly unavailable; a data failure surfaces as an explicit message, not a crash.
