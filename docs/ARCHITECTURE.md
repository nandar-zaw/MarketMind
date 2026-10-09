# MarketMind Architecture

MarketMind uses a simple multi-agent design that is easy to explain in class.

## High-Level Diagram (ASCII)

```text
                User
                  |
                  v
               FastAPI
                  |
                  v
           Coordinator Agent
                  |
    +-------------+-------------+
    |             |             |
    v             v             v
Technical     Sentiment    Fundamental
 Agent          Agent         Agent
    |             |             |
    +-------------+-------------+
                  |
                  v
              Risk Agent
                  |
                  v
         Final Recommendation
```

## Big-Picture Architecture (for class)

A fuller view including **DataAgent**, **guardrails**, and data supply. For slides and
talking points, see also `docs/PRESENTATION_AGENTS_AND_GUARDRAILS.md`.

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

    subgraph Specialists["Specialist voters"]
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
                 |                    |                    |
                 +--------------------+--------------------+
                                      v
                                 Risk Agent
                                      v
                         Coordinator blends votes
                                      v
                         Output guardrail --> BUY/HOLD/SELL
```

## Architecture (classroom-simple)

This Mermaid diagram shows the same flow more clearly, including how the
**DataAgent** supplies data to the analysis agents:

```mermaid
flowchart TD
    User --> FastAPI
    FastAPI --> Coordinator
    Coordinator --> DataAgent
    Coordinator --> TechnicalAgent
    Coordinator --> SentimentAgent
    Coordinator --> FundamentalAgent
    DataAgent -.->|supplies data| TechnicalAgent
    DataAgent -.->|supplies data| SentimentAgent
    DataAgent -.->|supplies data| FundamentalAgent
    TechnicalAgent --> RiskAgent
    SentimentAgent --> RiskAgent
    FundamentalAgent --> RiskAgent
    RiskAgent --> FinalRec[Final Recommendation]
```

**How to read it:**

- Solid arrows = main control flow (User → FastAPI → Coordinator → agents → Risk → final recommendation)
- Dashed arrows labeled "supplies data" = DataAgent feeds price/company data into Technical, Sentiment, and Fundamental agents
- RiskAgent reviews the specialized agent outputs before the final recommendation

## Data Agent Role

The **Data Collector Agent** is the shared market-data source for the pipeline.

The Coordinator loads DataAgent **once** per request, then shares the result:

- historical OHLCV prices → Technical Agent + Risk Agent
- recent news headlines → Sentiment Agent
- basic company / fund metadata → `DataAgentResult.company_info`
- fundamental metrics (yfinance API) → `DataAgentResult.fundamentals` for the Fundamental Agent

DataAgent does **not** use SEC file storage. File-storage RAG on the Fundamental
Agent is optional/legacy for single-stock demos; the S&P 500 path should read
fundamentals from DataAgent.

## Request Flow (Future)

1. The user sends a market symbol to FastAPI (for example `SPY` for the S&P 500).
2. FastAPI calls the **Coordinator Agent**.
3. The Coordinator asks specialized agents for their signals.
4. The **Risk Agent** reviews risk before the final decision.
5. MarketMind returns a structured recommendation:

   - BUY / HOLD / SELL
   - confidence score
   - short explanation
   - supporting evidence from each agent

## Why This Architecture?

- Each agent has one clear job (specialization).
- The Coordinator combines results (coordination).
- Outputs are structured with Pydantic models (explainability).
- The design stays small enough for a classroom presentation.

## Phase 1 Note

Phase 1 only creates the project structure and placeholder classes.
No real analysis or agent coordination runs yet.
