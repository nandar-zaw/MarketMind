"""
Data Collector Agent.

Retrieves historical OHLCV prices and basic company information
for other agents. Does not make investment decisions.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.agents.base_agent import BaseAgent
from app.models.schemas import DataAgentResult
from app.services.market_data import MarketDataService
from app.utils.exceptions import MarketDataError
from app.utils.helpers import normalize_ticker

logger = logging.getLogger(__name__)


class DataAgent(BaseAgent):
    """
    Download stock price data and basic company information.

    The analyze() method stays async to match BaseAgent, but the
    underlying MarketDataService / yfinance calls are synchronous.
    We call them directly (blocking) to keep the code simple and honest —
    yfinance is not a true async library.
    """

    name = "data_agent"

    def __init__(self, market_data_service: Optional[MarketDataService] = None):
        self.market_data = market_data_service or MarketDataService()

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
            ticker: Stock symbol (e.g. "AAPL" or "aapl").
            start: Optional start date YYYY-MM-DD.
            end: Optional end date YYYY-MM-DD.
            period: yfinance period used when start/end are omitted (default "1y").
            as_of_date: Optional cutoff date; no prices after this date are returned.

        Returns:
            DataAgentResult with company info and chronological OHLCV history.
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
        company_info = self.market_data.get_company_info(symbol)

        result = DataAgentResult(
            ticker=symbol,
            company_info=company_info,
            price_history=price_history,
            start_date=price_history[0].date if price_history else None,
            end_date=price_history[-1].date if price_history else None,
            records_count=len(price_history),
        )

        logger.info(
            "DataAgent completed for %s with %s records",
            symbol,
            result.records_count,
        )
        return result
