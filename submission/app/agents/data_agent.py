"""
Data Collector Agent.

Retrieves historical OHLCV prices, basic company / fund information,
fundamental metrics (direct market API), and recent news headlines for
other agents. Does not make investment decisions.

Fundamental metrics come from yfinance — not from SEC file storage.
The Fundamental Agent teammate can later score ``DataAgentResult.fundamentals``.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.agents.base_agent import BaseAgent
from app.models.schemas import CompanyInfo, DataAgentResult, FundamentalSnapshot
from app.services.market_data import MarketDataService
from app.services.news_data import NewsDataService
from app.utils.exceptions import MarketDataError
from app.utils.helpers import normalize_ticker

logger = logging.getLogger(__name__)


class DataAgent(BaseAgent):
    """
    Download market data and package it for specialist agents.

    The analyze() method stays async to match BaseAgent, but the
    underlying MarketDataService / yfinance calls are synchronous.
    We call them directly (blocking) to keep the code simple and honest —
    yfinance is not a true async library.
    """

    name = "data_agent"

    def __init__(
        self,
        market_data_service: Optional[MarketDataService] = None,
        news_data_service: Optional[NewsDataService] = None,
    ):
        self.market_data = market_data_service or MarketDataService()
        self.news_data = news_data_service or NewsDataService()

    async def analyze(
        self,
        ticker: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        period: str = "1y",
        as_of_date: Optional[str] = None,
    ) -> DataAgentResult:
        """
        Fetch and clean market data for a ticker.

        Args:
            ticker: Market symbol (default focus: "SPY" for the S&P 500).
            start: Optional start date YYYY-MM-DD.
            end: Optional end date YYYY-MM-DD.
            period: yfinance period used when start/end are omitted (default "1y").
            as_of_date: Optional cutoff date; no prices after this date are returned.

        Returns:
            DataAgentResult with company info, fundamentals, chronological
            OHLCV history, and recent news headlines.
        """
        if ticker is None or not str(ticker).strip():
            raise MarketDataError("Ticker must not be empty.")

        symbol = normalize_ticker(ticker)
        logger.info(
            "DataAgent analyzing %s (start=%s, end=%s, period=%s, as_of_date=%s)",
            symbol,
            start,
            end,
            period,
            as_of_date,
        )

        price_history = self.market_data.get_ohlcv(
            symbol,
            start=start,
            end=end,
            period=period,
            as_of_date=as_of_date,
        )

        # One Yahoo .info call for both metadata and fundamentals.
        try:
            company_info, fundamentals = self.market_data.get_company_and_fundamentals(
                symbol
            )
        except Exception as exc:
            logger.warning(
                "DataAgent: company/fundamentals fetch failed for %s (%s); "
                "continuing with empty metadata.",
                symbol,
                exc,
            )
            company_info = self._empty_company(symbol)
            fundamentals = FundamentalSnapshot(ticker=symbol)

        # News is supporting data (the Sentiment Agent consumes it).
        # A news outage must not fail the whole data pull.
        try:
            news = self.news_data.get_recent_news(symbol)
        except Exception as exc:
            logger.warning(
                "DataAgent: news fetch failed for %s (%s); continuing without headlines.",
                symbol,
                exc,
            )
            news = []

        result = DataAgentResult(
            ticker=symbol,
            company_info=company_info,
            price_history=price_history,
            news=news,
            fundamentals=fundamentals,
            start_date=price_history[0].date if price_history else None,
            end_date=price_history[-1].date if price_history else None,
            records_count=len(price_history),
        )

        logger.info(
            "DataAgent completed for %s with %s price records "
            "(fundamentals quote_type=%s)",
            symbol,
            result.records_count,
            getattr(fundamentals, "quote_type", None),
        )
        return result

    @staticmethod
    def _empty_company(symbol: str) -> CompanyInfo:
        return CompanyInfo(ticker=symbol)
