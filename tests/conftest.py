"""Shared pytest fixtures."""

import pytest


@pytest.fixture(autouse=True)
def isolated_decision_memory(tmp_path, monkeypatch):
    """Never write test decisions into the real decision-memory file."""
    monkeypatch.setenv("MARKETMIND_MEMORY_PATH", str(tmp_path / "memory.sqlite"))
