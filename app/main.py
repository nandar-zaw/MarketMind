"""
MarketMind FastAPI application.

Phase 1: health check and placeholder analyze endpoint only.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="MarketMind",
    description=(
        "A Multi-Agent System for S&P 500 Trend Prediction "
        "and Investment Decision Support"
    ),
    version="0.1.0",
)


@app.get("/health")
async def health():
    """Simple health check for Phase 1."""
    return {
        "status": "ok",
        "project": "MarketMind",
    }


@app.post("/analyze/{ticker}")
async def analyze(ticker: str):
    """
    Placeholder analysis endpoint.

    Real multi-agent analysis will be implemented in a later phase.
    """
    return JSONResponse(
        status_code=501,
        content={
            "detail": "MarketMind analysis will be implemented in a later phase.",
            "ticker": ticker.upper(),
        },
    )
