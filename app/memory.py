"""
Decision memory for the Coordinator.

Every final recommendation is saved to a small SQLite file, so the next
analysis of the same ticker can say what changed since last time.

This is long-term memory of *decisions*, not chat history. It never
changes the vote; it only adds context to the explanation. The stored
price at decision time also lets a later backtest check whether past
recommendations were right.

The file lives at data/marketmind_memory.sqlite (git-ignored). Set
MARKETMIND_MEMORY_PATH to use a different file.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.models.schemas import DecisionRecord, FinalRecommendation

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "marketmind_memory.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    analyzed_at TEXT NOT NULL,
    horizon_days INTEGER NOT NULL,
    recommendation TEXT NOT NULL,
    confidence REAL NOT NULL,
    risk_level TEXT,
    agent_signals TEXT NOT NULL,
    last_close REAL
)
"""

_COLUMNS = (
    "ticker, analyzed_at, horizon_days, recommendation, confidence, "
    "risk_level, agent_signals, last_close"
)


class DecisionMemory:
    """Save and look up past Coordinator decisions per ticker."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.getenv("MARKETMIND_MEMORY_PATH") or DEFAULT_PATH)

    def record(
        self,
        final: FinalRecommendation,
        last_close: float | None = None,
        analyzed_at: datetime | None = None,
    ) -> DecisionRecord:
        signals = {r.agent_name: r.signal for r in final.agent_results}
        record = DecisionRecord(
            ticker=final.ticker,
            analyzed_at=analyzed_at or datetime.now(timezone.utc),
            horizon_days=final.horizon_days,
            recommendation=final.recommendation,
            confidence=final.confidence,
            risk_level=signals.get("risk_agent"),
            agent_signals=signals,
            last_close=last_close,
        )
        with closing(self._connect()) as conn, conn:
            conn.execute(
                f"INSERT INTO decisions ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.ticker,
                    record.analyzed_at.isoformat(),
                    record.horizon_days,
                    record.recommendation,
                    record.confidence,
                    record.risk_level,
                    json.dumps(record.agent_signals),
                    record.last_close,
                ),
            )
        return record

    def last(self, ticker: str, horizon_days: int | None = None) -> DecisionRecord | None:
        """Most recent decision for a ticker (optionally for one horizon)."""
        query = f"SELECT {_COLUMNS} FROM decisions WHERE ticker = ?"
        params: list = [ticker.upper()]
        if horizon_days is not None:
            query += " AND horizon_days = ?"
            params.append(horizon_days)
        query += " ORDER BY id DESC LIMIT 1"
        with closing(self._connect()) as conn:
            row = conn.execute(query, params).fetchone()
        return _to_record(row) if row else None

    def history(self, ticker: str, limit: int = 20) -> list[DecisionRecord]:
        """Recent decisions for a ticker, newest first."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT {_COLUMNS} FROM decisions WHERE ticker = ? ORDER BY id DESC LIMIT ?",
                (ticker.upper(), limit),
            ).fetchall()
        return [_to_record(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.execute(_SCHEMA)
        return conn


def _to_record(row: tuple) -> DecisionRecord:
    ticker, analyzed_at, horizon, rec, conf, risk, signals, close = row
    return DecisionRecord(
        ticker=ticker,
        analyzed_at=datetime.fromisoformat(analyzed_at),
        horizon_days=horizon,
        recommendation=rec,
        confidence=conf,
        risk_level=risk,
        agent_signals=json.loads(signals),
        last_close=close,
    )
