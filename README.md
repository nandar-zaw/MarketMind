# MarketMind

**A Multi-Agent System for S&P 500 Trend Prediction and Investment Decision Support**

MarketMind is an academic course project for AI Engineering.
It is **not** a production trading system.

### Disclaimer (important)

**This is not financial advice.** MarketMind only produces educational
predictions / model signals for a course project. It does **not** advise
anyone to buy or sell any stock or ETF. You are solely responsible for any
decisions you make. The authors, developers, and affiliated institutions
accept **no responsibility or liability** for any loss, damage, or other
consequence arising from use of this software or its outputs.

The goal is to demonstrate:

- multi-agent AI concepts
- agent specialization
- coordination between agents
- structured outputs
- basic financial analysis
- explainable recommendations
- simple evaluation later

---

## How MarketMind Works

MarketMind uses several specialized AI agents.
Each agent studies a different type of information.

| Agent | What it looks at |
| --- | --- |
| **Data Collector Agent** | Downloads prices, company info, fundamentals, and headlines (yfinance) |
| **Technical Agent** | Looks at price trends (RSI, SMA, MACD) |
| **Sentiment Agent** | Looks at news sentiment (LLM if key set, else keyword fallback) |
| **Fundamental Agent** | Looks at yfinance fundamentals from DataAgent |
| **Risk Agent** | Looks at volatility and risk |
| **Coordinator Agent** | Combines the results into one recommendation |

### Final output

For the S&P 500 (symbol `SPY` on Yahoo Finance / yfinance), MarketMind returns:

- **BUY**, **HOLD**, or **SELL**
- a confidence score
- a short explanation
- supporting evidence from each agent

**Prediction horizon:** 5 trading days

---

## Current Status

Working today:

- FastAPI `/health` and `/analyze/{ticker}`
- Gradio dashboard with Plotly charts (1D–1Y windows)
- **Data Collector Agent** — OHLCV, info, fundamentals, headlines via yfinance
- Technical, Sentiment, Fundamental, Risk, and Coordinator agents
- input / tool / output guardrails (internal; not shown in the UI)
- `SPY` as the S&P 500 proxy (`^GSPC` / `SPX` aliases resolve to `SPY`)

Still later work:

- Phase 7 ML prediction model
- Phase 8 backtesting
- presentation polish

---

## Project Structure

```text
MarketMind/
├── README.md
├── requirements.txt
├── .env.example
├── app/
│   ├── main.py          # FastAPI entry
│   ├── ui.py            # Gradio dashboard
│   ├── models/
│   ├── agents/
│   ├── services/
│   ├── ml/
│   └── utils/
├── tests/
└── docs/
```

See also:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/AGENTS.md](docs/AGENTS.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)

---

## Setup

Requirements: **Python 3.12+**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Optional: copy `.env.example` to `.env`. An OpenAI key enables LLM sentiment;
without it, Sentiment uses a keyword fallback. Fundamentals do **not** require
a vector-store ID for SPY.

On Windows, if `python` is not on PATH, use `py -3.12` instead.

---

## How to Run

### Option A — Gradio dashboard (recommended)

From the repo root, with the venv active:

```bash
python -m app.ui
```

Then open the URL printed in the terminal (usually
[http://127.0.0.1:7860](http://127.0.0.1:7860)).

Pick a ticker (default `SPY`, or QQQ / NVDA / TSLA / AAPL / … — or type your
own), click **Analyze**, and explore chart windows without re-running analysis.

### Option B — FastAPI API

```bash
uvicorn app.main:app --reload
```

Then open:

- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Expected `/health` response:

```json
{
  "status": "ok",
  "project": "MarketMind"
}
```

Analyze the S&P 500 proxy:

```bash
# browser
http://127.0.0.1:8000/analyze/SPY

# or POST
curl -X POST http://127.0.0.1:8000/analyze/SPY
```

`SPY` is the S&P 500 ETF used as our market symbol. Aliases such as
`^GSPC` / `SPX` are resolved to `SPY` before analysis.

Try a rejected input to show an input guardrail:

```bash
curl http://127.0.0.1:8000/analyze/not-a-ticker
```

---

## How to Run Tests

```bash
pytest
```

---

## Roadmap (Short Version)

1. Project structure and placeholders (done)
2. Real stock data (DataAgent done) + Technical Agent (done)
3. News + Sentiment Agent (done)
4. Fundamental Agent (done)
5. Risk Agent (done)
6. Coordinator Agent (done)
7. Simple ML prediction model
8. Simple backtesting
9. Dashboard (Gradio done)
10. Final testing and presentation

Full details: [docs/ROADMAP.md](docs/ROADMAP.md)
