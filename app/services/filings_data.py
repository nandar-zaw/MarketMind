"""
Filing evidence service.

Retrieves passages from the SEC filings (10-K / 10-Q) stored in the
project's OpenAI vector store, so the Fundamental Analysis Agent can
reason over filing evidence without querying the store itself. This
is data-layer code, mirroring NewsDataService: analysis agents never
call retrieval providers directly. They receive filing excerpts
through the Data Collector Agent (DataAgentResult.filings).

Configuration: FUNDAMENTALS_VECTOR_STORE_ID in .env (see
.env.example). When it is not set, the service returns an empty list
and the Fundamental Agent reports "unavailable" instead of failing.

Retrieval is semantic across the whole store, so excerpts can in
principle come from another company's filing; the excerpts carry
their source file name, and the Fundamental Agent is instructed to
use only excerpts about the requested ticker (the same discipline
the previous FileSearchTool setup relied on).
"""

from __future__ import annotations

import logging
import os
import time

from app.models.schemas import FilingExcerpt
from app.utils.exceptions import MarketDataError

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30 * 60
_TEXT_LIMIT = 1500
_QUERY = (
    "{ticker}: revenue growth, gross margin, operating margin, "
    "cash position, total debt, valuation, risk factors"
)

# ticker -> (monotonic timestamp, normalized excerpts). Filings do
# not change minute to minute, so the cache lives at module level,
# mirroring NewsDataService.
_CACHE: dict[str, tuple[float, list[FilingExcerpt]]] = {}


def _part_text(part) -> str:
    if isinstance(part, dict):
        return str(part.get("text") or "")
    return str(getattr(part, "text", "") or "")


def _normalize_item(item) -> FilingExcerpt | None:
    """Normalize one vector-store search result (SDK object or dict)."""
    if isinstance(item, dict):
        content = item.get("content") or []
        source = item.get("filename") or item.get("file_id") or ""
        score = item.get("score")
    else:
        content = getattr(item, "content", None) or []
        source = getattr(item, "filename", None) or getattr(item, "file_id", "") or ""
        score = getattr(item, "score", None)
    text = "\n".join(t for t in (_part_text(p) for p in content) if t).strip()
    if not text:
        return None
    try:
        score = float(score) if score is not None else None
    except (TypeError, ValueError):
        score = None
    return FilingExcerpt(
        text=text[:_TEXT_LIMIT],
        source=str(source),
        score=score,
    )


class FilingsDataService:
    """
    SEC filing evidence retrieval for one ticker at a time.

    Synchronous, like the other data services: the DataAgent calls
    this directly (blocking) to keep the code simple and honest.
    """

    def __init__(self, searcher=None, vector_store_id: str | None = None):
        # Injectable raw searcher for tests:
        # searcher(vector_store_id, query, limit) -> raw result items.
        # Defaults to the OpenAI vector store search API.
        self._searcher = searcher
        self._vector_store_id = vector_store_id

    def get_filing_evidence(
        self, ticker: str, limit: int = 8
    ) -> list[FilingExcerpt]:
        """
        Return up to ``limit`` filing excerpts relevant to a ticker.

        Returns an empty list when the vector store is not configured
        (FUNDAMENTALS_VECTOR_STORE_ID unset). Raises MarketDataError
        for an empty ticker or a provider failure; callers that treat
        filings as supporting data (the DataAgent) catch it and
        continue with an empty list.
        """
        symbol = (ticker or "").strip().upper()
        if not symbol:
            raise MarketDataError("Ticker must not be empty.")

        store_id = self._vector_store_id or os.getenv(
            "FUNDAMENTALS_VECTOR_STORE_ID"
        )
        if not store_id:
            logger.info(
                "FilingsDataService: FUNDAMENTALS_VECTOR_STORE_ID is not "
                "set; no filing evidence for %s.",
                symbol,
            )
            return []

        cached = _CACHE.get(symbol)
        if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1][:limit]

        try:
            raw = self._search_raw(store_id, _QUERY.format(ticker=symbol), limit)
        except Exception as exc:
            raise MarketDataError(
                f"Provider failure for {symbol} filing evidence: {exc}"
            ) from exc

        excerpts: list[FilingExcerpt] = []
        for item in raw:
            normalized = _normalize_item(item)
            if normalized is not None:
                excerpts.append(normalized)

        if excerpts:
            # Only cache real coverage, mirroring NewsDataService: an
            # empty response may be a transient provider hiccup.
            _CACHE[symbol] = (time.monotonic(), excerpts)
            logger.info(
                "FilingsDataService fetched %d excerpts for %s",
                len(excerpts),
                symbol,
            )
        else:
            logger.warning(
                "FilingsDataService got 0 usable excerpts for %s", symbol
            )
        return excerpts[:limit]

    def _search_raw(self, vector_store_id: str, query: str, limit: int) -> list:
        if self._searcher is not None:
            return self._searcher(vector_store_id, query, limit) or []
        from openai import OpenAI

        client = OpenAI()
        response = client.vector_stores.search(
            vector_store_id=vector_store_id,
            query=query,
            max_num_results=limit,
        )
        return list(getattr(response, "data", None) or [])
