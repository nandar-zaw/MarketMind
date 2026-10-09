"""
MarketMind FastAPI application.

Serves the analyze API (Coordinator + Risk Manager with input /
tool / output guardrails) and mounts the Gradio UI at "/" so a
single process (for example one Heroku dyno) exposes both.
"""

import inspect

import gradio as gr
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.agents.coordinator_agent import CoordinatorAgent
from app.guardrails import GuardrailTripwire
from app.ui import _CSS, _THEME
from app.ui import demo as gradio_demo

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


# Mount the Gradio UI at the root so one process serves the API
# (/health, /analyze/{ticker}) and the interactive dashboard.
# Gradio 6 takes theme/css at mount time (the Blocks arguments are
# ignored when mounted); Gradio 5 reads them from the Blocks object.
_mount_kwargs = {}
if "theme" in inspect.signature(gr.mount_gradio_app).parameters:
    _mount_kwargs = {"theme": _THEME, "css": _CSS}
app = gr.mount_gradio_app(app, gradio_demo, path="/", **_mount_kwargs)
