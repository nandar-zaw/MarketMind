"""
News data service.

Fetches recent company news headlines for sentiment analysis, backed
by yfinance (the same provider as MarketDataService, so no extra API
key is needed). This is data-layer code: analysis agents never call
news providers directly. They receive headlines through the Data
Collector Agent (DataAgentResult.news).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from app.models.schemas import NewsItem
from app.utils.exceptions import MarketDataError

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30 * 60
_SUMMARY_LIMIT = 400

# ticker -> (monotonic timestamp, normalized items). Headlines do not
# change minute to minute, and services are re-instantiated per call,
# so the cache lives at module level.
_CACHE: dict[str, tuple[float, list[NewsItem]]] = {}


def _normalize_item(item) -> NewsItem | None:
    """Normalize one yfinance news item (new or legacy shape)."""
    if not isinstance(item, dict):
        return None
    content = item.get("content") or {}
    title = (content.get("title") or item.get("title") or "").strip()
    if not title:
        return None
    provider = content.get("provider") or {}
    publisher = (
        provider.get("displayName") or item.get("publisher") or "Unknown source"
    )
    published = str(content.get("pubDate") or "")[:10] or None
    if published is None and item.get("providerPublishTime"):
        try:
            published = datetime.fromtimestamp(
                float(item["providerPublishTime"]), tz=timezone.utc
            ).date().isoformat()
        except (TypeError, ValueError, OSError):
            published = None
    summary = (content.get("summary") or item.get("summary") or "").strip()
    return NewsItem(
        title=title,
        publisher=str(publisher),
        published=published,
        summary=summary[:_SUMMARY_LIMIT],
    )


class NewsDataService:
    """
    Recent-news retrieval for one ticker at a time.

    Synchronous, like MarketDataService: yfinance is not a true async
    library, and the DataAgent calls this directly (blocking) to keep
    the code simple and honest.
    """

    def __init__(self, fetcher=None):
        # Injectable raw fetcher for tests: fetcher(ticker) -> list of
        # raw provider items. Defaults to yfinance.
        self._fetcher = fetcher

    def get_recent_news(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        """
        Return up to ``limit`` recent headlines for a ticker,
        in the provider's order (newest first for yfinance).

        Raises MarketDataError for an empty ticker or a provider
        failure; callers that treat news as supporting data (the
        DataAgent) catch it and continue with an empty list.
        """
        symbol = (ticker or "").strip().upper()
        if not symbol:
            raise MarketDataError("Ticker must not be empty.")

        cached = _CACHE.get(symbol)
        if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1][:limit]

        try:
            raw = self._fetch_raw(symbol)
        except Exception as exc:
            raise MarketDataError(
                f"Provider failure for {symbol} news: {exc}"
            ) from exc

        items: list[NewsItem] = []
        for item in raw:
            normalized = _normalize_item(item)
            if normalized is not None:
                items.append(normalized)

        _CACHE[symbol] = (time.monotonic(), items)
        logger.info(
            "NewsDataService fetched %d headlines for %s", len(items), symbol
        )
        return items[:limit]

    def _fetch_raw(self, ticker: str) -> list:
        if self._fetcher is not None:
            return self._fetcher(ticker) or []
        import yfinance as yf

        return yf.Ticker(ticker).news or []
