"""
MarketMind FastAPI application.

Phase 1 health check plus a working analyze endpoint driven by
Coordinator + Risk Manager (with input / tool / output guardrails).
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.agents.coordinator_agent import CoordinatorAgent
from app.guardrails import GuardrailTripwire, input_guardrail
from app.memory import DecisionMemory

app = FastAPI(
    title="MarketMind",
    description=(
        "A Multi-Agent System for S&P 500 Trend Prediction "
        "and Investment Decision Support"
    ),
    version="0.2.0",
)


@app.get("/health")
async def health():
    """Simple health check."""
    return {
        "status": "ok",
        "project": "MarketMind",
    }


async def _run_analysis(ticker: str, horizon_days: int = 5):
    coordinator = CoordinatorAgent()
    try:
        result = await coordinator.analyze(ticker, horizon_days=horizon_days)
    except GuardrailTripwire as exc:
        return JSONResponse(
            status_code=400,
            content={
                "detail": exc.detail,
                "guardrail_kind": exc.kind,
                "guardrail_name": exc.name,
                "ticker": str(ticker).upper() if ticker else "",
            },
        )
    return result


@app.get("/analyze/{ticker}")
@app.post("/analyze/{ticker}")
async def analyze(ticker: str, horizon_days: int = 5):
    """
    Run Coordinator + Risk Manager and return a structured recommendation.

    GET is provided so a professor can open the URL in a browser.
    POST remains the main API style.
    """
    return await _run_analysis(ticker, horizon_days=horizon_days)


@app.get("/history/{ticker}")
async def history(ticker: str, limit: int = 20):
    """Past Coordinator decisions for a ticker from decision memory, newest first."""
    try:
        symbol, _ = input_guardrail(ticker)
    except GuardrailTripwire as exc:
        return JSONResponse(
            status_code=400,
            content={
                "detail": exc.detail,
                "guardrail_kind": exc.kind,
                "guardrail_name": exc.name,
            },
        )
    limit = max(1, min(limit, 100))
    return {"ticker": symbol, "decisions": DecisionMemory().history(symbol, limit=limit)}
