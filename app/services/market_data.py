"""
Market data service.

Downloads recent OHLCV prices. The Coordinator calls this through a
tool guardrail so agents cannot request arbitrary lookbacks or tools.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd


class MarketDataError(Exception):
    """Raised when price history cannot be downloaded."""


class MarketDataService:
    """Stock price access used by Risk Manager and Coordinator."""

    def get_price_history(self, ticker: str, days: int = 90) -> pd.DataFrame:
        """
        Return recent OHLCV data for a ticker.

        Uses yfinance. The caller must already have passed tool guardrails.
        """
        try:
            import yfinance as yf
        except ImportError as exc:
            raise MarketDataError(
                "yfinance is not installed. Run: pip install -r requirements.txt"
            ) from exc

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days + 10)
        frame = yf.download(
            ticker,
            start=start.date().isoformat(),
            end=end.date().isoformat(),
            auto_adjust=True,
            progress=False,
        )
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

    def get_company_info(self, ticker: str):
        """Company info stays for the Data Collector Agent (later)."""
        raise NotImplementedError(
            "Company info lookup will be implemented with the Data Agent."
        )
