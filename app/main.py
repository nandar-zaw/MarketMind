"""
MarketMind FastAPI application.

Serves the analyze API (Coordinator + Risk Manager with input /
tool / output guardrails) and mounts the Gradio UI at "/" so a
single process (for example one Heroku dyno) exposes both.

Because the deployed demo is a public, unauthenticated endpoint that
spends OpenAI quota per call, ``/analyze`` has two cheap, course-
appropriate protections (both configurable via environment):

- a soft in-process rate limit per client IP (``ANALYZE_RATE_LIMIT``
  calls per ``ANALYZE_RATE_WINDOW_SECONDS``), and
- an optional shared demo token (``DEMO_API_TOKEN``); when set, callers
  must send it in the ``X-Demo-Token`` header.

The mounted dashboard calls the Coordinator in-process, so these guards
apply to the REST API only.
"""

import inspect
import os
import time
from collections import defaultdict, deque

import gradio as gr
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from app.agents.coordinator_agent import CoordinatorAgent
from app.guardrails import GuardrailTripwire
from app.ui import _CUSTOM_CSS as _UI_CSS
from app.ui import demo as gradio_demo
from app.ui import theme as _UI_THEME

_APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
_DOCS_ENABLED = _APP_ENV not in {"production", "prod"}

app = FastAPI(
    title="MarketMind",
    description=(
        "A Multi-Agent System for S&P 500 Trend Prediction "
        "and Investment Decision Support"
    ),
    version="0.2.0",
    # Hide the interactive schema in production to reduce surface area.
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
)

# client key -> monotonic timestamps of recent accepted calls.
_ANALYZE_HITS: dict[str, deque[float]] = defaultdict(deque)


@app.get("/health")
async def health():
    """Simple health check."""
    return {
        "status": "ok",
        "project": "MarketMind",
    }


def _rate_limit_config() -> tuple[int, int]:
    """(limit, window_seconds) for /analyze; limit <= 0 disables it."""
    try:
        limit = int(os.getenv("ANALYZE_RATE_LIMIT", "30"))
    except ValueError:
        limit = 30
    try:
        window = int(os.getenv("ANALYZE_RATE_WINDOW_SECONDS", "60"))
    except ValueError:
        window = 60
    return limit, max(1, window)


def _rate_limit_retry_after(client_key: str) -> int | None:
    """Record a hit; return seconds to wait when the limit is exceeded."""
    limit, window = _rate_limit_config()
    if limit <= 0:
        return None
    now = time.monotonic()
    hits = _ANALYZE_HITS[client_key]
    while hits and now - hits[0] > window:
        hits.popleft()
    if len(hits) >= limit:
        return max(1, int(window - (now - hits[0])))
    hits.append(now)
    return None


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
async def analyze(
    request: Request,
    ticker: str,
    horizon_days: int = 5,
    x_demo_token: str | None = Header(default=None),
):
    """
    Run Coordinator + Risk Manager and return a structured recommendation.

    GET is provided so a professor can open the URL in a browser.
    POST remains the main API style.
    """
    expected_token = os.getenv("DEMO_API_TOKEN")
    if expected_token and x_demo_token != expected_token:
        return JSONResponse(
            status_code=401,
            content={"detail": "A valid X-Demo-Token header is required."},
        )

    client_key = request.client.host if request.client else "unknown"
    retry_after = _rate_limit_retry_after(client_key)
    if retry_after is not None:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={
                "detail": (
                    "Too many analyze requests from this client. "
                    "Please wait and try again."
                ),
                "retry_after_seconds": retry_after,
            },
        )

    return await _run_analysis(ticker, horizon_days=horizon_days)


# Mount the Gradio UI at the root so one process serves the API
# (/health, /analyze/{ticker}) and the interactive dashboard.
# Gradio 6 takes theme/css at mount time (the Blocks arguments are
# ignored when mounted); Gradio 5 reads them from the Blocks object.
_mount_kwargs = {}
if "theme" in inspect.signature(gr.mount_gradio_app).parameters:
    _mount_kwargs = {"theme": _UI_THEME, "css": _UI_CSS}
app = gr.mount_gradio_app(app, gradio_demo, path="/", **_mount_kwargs)
