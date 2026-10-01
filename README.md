# MarketMind

**A Multi-Agent System for S&P 500 Trend Prediction and Investment Decision Support**

MarketMind is an academic course project for AI Engineering.
It is **not** a production trading system.

The goal is to demonstrate:

- multi-agent AI concepts
- agent specialization
- coordination between agents
- structured outputs
- basic financial analysis
- explainable recommendations
- simple evaluation later

---

## How MarketMind Works (Future Design)

MarketMind uses several specialized AI agents.
Each agent studies a different type of information.

| Agent | What it looks at |
| --- | --- |
| **Data Collector Agent** | Downloads stock prices and basic company info |
| **Technical Agent** | Looks at price trends (RSI, SMA, MACD) |
| **Sentiment Agent** | Looks at news sentiment |
| **Fundamental Agent** | Looks at company financial information |
| **Risk Agent** | Looks at volatility and risk |
| **Coordinator Agent** | Combines the results into one recommendation |

### Future final output

For a given ticker (for example `AAPL`), MarketMind will return:

- **BUY**, **HOLD**, or **SELL**
- a confidence score
- a short explanation
- supporting evidence from each agent

**Prediction horizon:** 5 trading days

---

## Phase 1 Status

**Phase 1 currently contains only project scaffolding.**

This means:

- folder structure exists
- FastAPI app starts
- `/health` works
- agent placeholder classes exist
- Pydantic models exist
- documentation exists
- basic tests pass

Phase 1 does **not** yet:

- call market APIs
- fetch real news
- calculate technical indicators
- train machine learning models
- call an LLM
- create real buy/sell recommendations
- run backtesting

---

## Project Structure

```text
MarketMind/
├── README.md
├── requirements.txt
├── .env.example
├── app/
│   ├── main.py
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

---

## How to Run

Start the FastAPI app:

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

The analyze endpoint is a placeholder for later phases:

```bash
POST /analyze/{ticker}
```

It currently returns **HTTP 501 Not Implemented**.

---

## How to Run Tests

```bash
pytest
```

---

## Roadmap (Short Version)

1. Project structure and placeholders (this phase)
2. Real stock data + Technical Agent
3. News + Sentiment Agent
4. Fundamental Agent
5. Risk Agent
6. Coordinator Agent
7. Simple ML prediction model
8. Simple backtesting
9. Dashboard
10. Final testing and presentation

Full details: [docs/ROADMAP.md](docs/ROADMAP.md)
