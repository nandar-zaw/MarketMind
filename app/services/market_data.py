"""
Market data service.

Downloads recent OHLCV prices for the Coordinator / Risk Manager, and
provides structured OHLCV history, company info, and fundamental metrics
for the Data Collector Agent (direct yfinance API — no file storage).

All external market-data access is isolated here so the provider
can be replaced later without changing agents.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd
import yfinance as yf

from app.models.schemas import CompanyInfo, FundamentalSnapshot, MarketPrice
from app.utils.exceptions import MarketDataError
from app.utils.helpers import normalize_ticker

logger = logging.getLogger(__name__)

# Approximate lookback used when as_of_date forces a calendar end date.
_DEFAULT_LOOKBACK_DAYS = 365


def _parse_date(value: str, field_name: str) -> date:
    """Parse a YYYY-MM-DD date string into a date object."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise MarketDataError(
            f"Invalid {field_name}: expected YYYY-MM-DD, got {value!r}."
        ) from exc


def _validate_ticker(ticker: str) -> str:
    """Reject empty tickers and return a normalized uppercase symbol."""
    if ticker is None or not str(ticker).strip():
        raise MarketDataError("Ticker must not be empty.")
    return normalize_ticker(ticker)


def _optional_float(value: Any) -> Optional[float]:
    """Convert a provider value to float, or None if missing/invalid."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


class MarketDataService:
    """
    Stock price and company data access.

    ``get_price_history`` returns a DataFrame for the Coordinator / Risk
    Manager tool path. ``get_ohlcv`` returns structured ``MarketPrice``
    models for the Data Collector Agent.
    """

    def get_price_history(self, ticker: str, days: int = 90) -> pd.DataFrame:
        """
        Return recent OHLCV data for a ticker as a DataFrame.

        Uses yfinance. The caller must already have passed tool guardrails.
        """
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days + 10)

        logger.info("Fetching %s days of price history for %s", days, ticker)
        try:
            frame = yf.download(
                ticker,
                start=start.date().isoformat(),
                end=end.date().isoformat(),
                auto_adjust=True,
                progress=False,
            )
        except Exception as exc:
            logger.error("Provider failure for %s price history: %s", ticker, exc)
            raise MarketDataError(
                f"Failed to fetch price history for {ticker}."
            ) from exc

        if frame is None or frame.empty:
            raise MarketDataError(f"No price history returned for {ticker}.")

        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)

        frame = frame.rename(columns=str.title)
        required = ["Close"]
        missing = [col for col in required if col not in frame.columns]
        if missing:
            raise MarketDataError(
                f"Price history for {ticker} is missing columns: {missing}"
            )
        return frame.dropna(subset=["Close"]).tail(days)

    def get_ohlcv(
        self,
        ticker: str,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        period: str = "1y",
        as_of_date: Optional[str] = None,
    ) -> list[MarketPrice]:
        """
        Return structured historical OHLCV data for a ticker.

        Default period is approximately one year (`period="1y"`)
        when start/end are not provided.

        When `as_of_date` is set, no observations after that date
        are returned (prevents future-data leakage for backtesting).
        """
        symbol = _validate_ticker(ticker)

        start_date = _parse_date(start, "start") if start else None
        end_date = _parse_date(end, "end") if end else None
        as_of = _parse_date(as_of_date, "as_of_date") if as_of_date else None
        use_period = start_date is None and end_date is None and as_of is None

        # Clamp the fetch end so we do not request future data.
        if as_of is not None:
            if end_date is None or end_date > as_of:
                end_date = as_of
            # Keep a ~1 year window ending at as_of when the caller
            # did not supply an explicit start date.
            if start_date is None:
                start_date = as_of - timedelta(days=_DEFAULT_LOOKBACK_DAYS)

        logger.info(
            "Fetching OHLCV for %s (start=%s, end=%s, period=%s, as_of=%s)",
            symbol,
            start_date,
            end_date,
            period if use_period else None,
            as_of,
        )

        try:
            yf_ticker = yf.Ticker(symbol)
            if use_period:
                frame = yf_ticker.history(period=period)
            else:
                # yfinance end is exclusive; add one day so the end date is included.
                download_end = None
                if end_date is not None:
                    download_end = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
                download_start = (
                    start_date.strftime("%Y-%m-%d") if start_date else None
                )
                frame = yf_ticker.history(start=download_start, end=download_end)
        except MarketDataError:
            raise
        except Exception as exc:
            logger.error("Provider failure for %s OHLCV: %s", symbol, exc)
            raise MarketDataError(
                f"Failed to fetch price history for {symbol}."
            ) from exc

        if frame is None or frame.empty:
            raise MarketDataError(
                f"No historical market data found for ticker '{symbol}'."
            )

        prices = self._dataframe_to_prices(frame, as_of=as_of)

        if not prices:
            raise MarketDataError(
                f"No usable OHLCV rows for ticker '{symbol}' after cleaning"
                + (f" and as_of_date={as_of}." if as_of else ".")
            )

        logger.info(
            "Retrieved %s price records for %s (%s to %s)",
            len(prices),
            symbol,
            prices[0].date,
            prices[-1].date,
        )
        return prices

    def _fetch_yahoo_info(self, symbol: str) -> dict:
        """Fetch the raw yfinance ``.info`` dict for one symbol."""
        try:
            info = yf.Ticker(symbol).info or {}
        except Exception as exc:
            logger.error("Provider failure for %s Yahoo info: %s", symbol, exc)
            raise MarketDataError(
                f"Failed to fetch market info for {symbol}."
            ) from exc
        if not isinstance(info, dict):
            return {}
        return info

    def get_company_info(self, ticker: str) -> CompanyInfo:
        """
        Return basic company / fund metadata for a ticker.

        Missing fields are returned as None rather than raising errors.
        """
        symbol = _validate_ticker(ticker)
        logger.info("Fetching company info for %s", symbol)
        info = self._fetch_yahoo_info(symbol)
        return self._map_company_info(symbol, info)

    def get_fundamentals(self, ticker: str) -> FundamentalSnapshot:
        """
        Return fundamental metrics from the direct market-data API.

        This is the DataAgent path for Fundamental Agent inputs
        (valuation, growth, balance-sheet style fields). It does **not**
        use SEC file storage or a vector store.

        Missing fields stay None (expected for ETFs such as SPY).
        """
        symbol = _validate_ticker(ticker)
        logger.info("Fetching fundamentals for %s", symbol)
        info = self._fetch_yahoo_info(symbol)
        return self._map_fundamentals(symbol, info)

    def get_company_and_fundamentals(
        self, ticker: str
    ) -> tuple[CompanyInfo, FundamentalSnapshot]:
        """
        Fetch company metadata and fundamentals with one Yahoo ``.info`` call.
        """
        symbol = _validate_ticker(ticker)
        logger.info("Fetching company info + fundamentals for %s", symbol)
        info = self._fetch_yahoo_info(symbol)
        return self._map_company_info(symbol, info), self._map_fundamentals(symbol, info)

    def _map_company_info(self, symbol: str, info: dict) -> CompanyInfo:
        company_name = info.get("longName") or info.get("shortName")
        return CompanyInfo(
            ticker=symbol,
            company_name=company_name,
            sector=info.get("sector"),
            industry=info.get("industry"),
            exchange=info.get("exchange"),
            currency=info.get("currency"),
            market_cap=_optional_float(info.get("marketCap")),
        )

    def _map_fundamentals(self, symbol: str, info: dict) -> FundamentalSnapshot:
        # dividendYield / yield: yfinance may expose either key for ETFs.
        dividend_yield = _optional_float(info.get("dividendYield"))
        if dividend_yield is None:
            dividend_yield = _optional_float(info.get("yield"))

        return FundamentalSnapshot(
            ticker=symbol,
            quote_type=info.get("quoteType"),
            trailing_pe=_optional_float(info.get("trailingPE")),
            forward_pe=_optional_float(info.get("forwardPE")),
            price_to_book=_optional_float(info.get("priceToBook")),
            price_to_sales=_optional_float(info.get("priceToSalesTrailing12Months")),
            dividend_yield=dividend_yield,
            profit_margins=_optional_float(info.get("profitMargins")),
            operating_margins=_optional_float(info.get("operatingMargins")),
            revenue_growth=_optional_float(info.get("revenueGrowth")),
            earnings_growth=_optional_float(info.get("earningsGrowth")),
            return_on_equity=_optional_float(info.get("returnOnEquity")),
            debt_to_equity=_optional_float(info.get("debtToEquity")),
            total_cash=_optional_float(info.get("totalCash")),
            total_debt=_optional_float(info.get("totalDebt")),
            beta=_optional_float(info.get("beta")),
            fifty_two_week_high=_optional_float(info.get("fiftyTwoWeekHigh")),
            fifty_two_week_low=_optional_float(info.get("fiftyTwoWeekLow")),
            total_assets=_optional_float(info.get("totalAssets")),
            ytd_return=_optional_float(info.get("ytdReturn")),
            three_year_avg_return=_optional_float(info.get("threeYearAverageReturn")),
        )

    def _dataframe_to_prices(
        self,
        frame: pd.DataFrame,
        *,
        as_of: Optional[date] = None,
    ) -> list[MarketPrice]:
        """Convert a yfinance history DataFrame into MarketPrice models."""
        # Ensure chronological order (oldest first).
        frame = frame.sort_index()

        required = ["Open", "High", "Low", "Close", "Volume"]
        for column in required:
            if column not in frame.columns:
                raise MarketDataError(
                    f"Price history is missing required column '{column}'."
                )

        prices: list[MarketPrice] = []
        has_adj = "Adj Close" in frame.columns

        for index, row in frame.iterrows():
            # Index may be a Timestamp (tz-aware) or a date-like value.
            if hasattr(index, "date"):
                row_date = index.date()
            else:
                row_date = pd.Timestamp(index).date()

            if as_of is not None and row_date > as_of:
                continue

            open_, high, low, close, volume = (
                row["Open"],
                row["High"],
                row["Low"],
                row["Close"],
                row["Volume"],
            )

            # Drop unusable rows with missing critical values.
            if pd.isna(open_) or pd.isna(high) or pd.isna(low) or pd.isna(close):
                continue
            if pd.isna(volume):
                continue

            adj_close = None
            if has_adj and not pd.isna(row["Adj Close"]):
                adj_close = float(row["Adj Close"])

            prices.append(
                MarketPrice(
                    date=row_date,
                    open=float(open_),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=int(volume),
                    adj_close=adj_close,
                )
            )

        return prices
