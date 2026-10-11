# MarketMind Architecture

MarketMind uses a simple multi-agent design that is easy to explain in class.

**Status:** Working end-to-end (DataAgent → parallel specialists → Risk →
Coordinator decision + guardrails). UI: Gradio; API: FastAPI.

For slide talking points, see also
[`PRESENTATION_AGENTS_AND_GUARDRAILS.md`](PRESENTATION_AGENTS_AND_GUARDRAILS.md).

---

## High-Level Diagram (ASCII)

```text
                User
                  |
                  v
         FastAPI / Gradio UI
                  |
                  v
           Coordinator Agent
                  |
                  v
             DataAgent (once)
          prices / news / fundamentals
                  |
     +------------+------------+
     |            |            |     ← parallel
     v            v            v
 Technical   Sentiment   Fundamental
     |            |            |
     +------------+------------+
                  |
                  v
              Risk Agent
                  |
                  v
     Coordinator blends votes
                  |
                  v
         Output guardrail
                  |
                  v
         Final Recommendation
            BUY / HOLD / SELL
```

---

## Big-Picture Architecture (for class)

```mermaid
flowchart TB
    subgraph Entry["Entry"]
        User["User<br/>ticker e.g. SPY"]
        UI["FastAPI / Gradio UI"]
    end

    subgraph Safety["Guardrails"]
        IG["1 Input guardrail"]
        TG["2 Tool + tool-output guardrail"]
        OG["6 Decision output guardrail"]
    end

    subgraph Orch["Orchestration"]
        Coord["Coordinator Agent"]
    end

    subgraph DataLayer["Shared data once per request"]
        Data["Data Collector Agent"]
    end

    subgraph Specialists["Specialist voters (parallel)"]
        Tech["Technical Agent"]
        Sent["Sentiment Agent"]
        Fund["Fundamental Agent"]
    end

    Risk["Risk Manager Agent"]
    Result["Final Recommendation<br/>BUY / HOLD / SELL"]

    User --> UI --> IG --> Coord
    Coord --> TG --> Data
    Data -.->|prices| Tech
    Data -.->|news| Sent
    Data -.->|fundamentals| Fund
    Tech --> Coord
    Sent --> Coord
    Fund --> Coord
    Coord --> Risk --> Coord
    Coord --> OG --> Result
```

```text
User --> UI --> Input guardrail --> Coordinator
                                      |
                    Tool guardrail --> DataAgent (once)
                                      | prices / news / fundamentals
                 +--------------------+--------------------+
                 v                    v                    v
            Technical            Sentiment            Fundamental
                 |                    |                    |  (parallel)
                 +--------------------+--------------------+
                                      v
                                 Risk Agent
                                      v
                         Coordinator blends votes
                                      v
                         Output guardrail --> BUY/HOLD/SELL
```

---

## Classroom Mermaid (control + data supply)

```mermaid
flowchart TD
    User --> UI[FastAPI / Gradio]
    UI --> Coordinator
    Coordinator --> DataAgent
    Coordinator --> TechnicalAgent
    Coordinator --> SentimentAgent
    Coordinator --> FundamentalAgent
    DataAgent -.->|supplies data| TechnicalAgent
    DataAgent -.->|supplies data| SentimentAgent
    DataAgent -.->|supplies data| FundamentalAgent
    TechnicalAgent --> Coordinator
    SentimentAgent --> Coordinator
    FundamentalAgent --> Coordinator
    Coordinator --> RiskAgent
    RiskAgent --> Coordinator
    Coordinator --> FinalRec[Final Recommendation]
```

**How to read it:**

- Solid arrows = control flow under the Coordinator
- Dashed arrows = DataAgent supplies shared market data
- Technical / Sentiment / Fundamental run **in parallel** after DataAgent
- Risk runs **after** those three finish
- The **Coordinator** (not Risk alone) produces BUY / HOLD / SELL; the
  decision output guardrail may adjust it (e.g. HIGH risk blocks BUY)

---

## Data Agent Role

The **Data Collector Agent** is the shared market-data source for the pipeline.

The Coordinator loads DataAgent **once** per request, then shares the result:

- historical OHLCV prices → Technical Agent + Risk Agent
- recent news headlines → Sentiment Agent (Yahoo Finance via yfinance)
- basic company / fund metadata → `DataAgentResult.company_info`
- fundamental metrics (yfinance `.info`) → `DataAgentResult.fundamentals`
  for the Fundamental Agent

DataAgent does **not** use SEC file storage. Optional vector-store RAG is
legacy for single-stock experiments; the default path reads fundamentals
from DataAgent.

---

## Request Flow (current)

1. User picks a ticker (default `SPY`) in Gradio, or calls
   `GET`/`POST /analyze/{ticker}` on FastAPI.
2. **Input guardrail** validates ticker + horizon.
3. Coordinator asks **DataAgent** once (tool guardrails around the fetch).
4. **Technical, Sentiment, and Fundamental** run **in parallel** on that
   shared data.
5. **Risk Agent** scores LOW / MEDIUM / HIGH from prices (+ optional
   bearish flags from Sentiment / Fundamental).
6. Coordinator blends votes into a draft BUY / HOLD / SELL.
7. **Decision output guardrail** validates (and may rewrite) the answer.
8. MarketMind returns a structured recommendation:

   - BUY / HOLD / SELL
   - confidence score
   - short explanation
   - supporting evidence from each agent

**Prediction horizon:** typically 5 trading days (UI also offers 3 / 10).

---

## Why This Architecture?

- Each agent has one clear job (specialization).
- The Coordinator combines results (orchestration).
- Specialists fan out in parallel on shared data (efficiency + clear votes).
- Outputs are structured with Pydantic models (explainability).
- Guardrails wrap input, tools, and outputs (classroom safety pattern).
- The design stays small enough for a course presentation.

---

## Related docs

| Doc | Purpose |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Per-agent roles and I/O |
| [`DATA_AGENT.md`](DATA_AGENT.md) | DataCollector deep dive |
| [`TECHNICAL_AGENT.md`](TECHNICAL_AGENT.md) | Technical indicators |
| [`PRESENTATION_AGENTS_AND_GUARDRAILS.md`](PRESENTATION_AGENTS_AND_GUARDRAILS.md) | Presentation script |
| [`ROADMAP.md`](ROADMAP.md) | Phase checklist |
