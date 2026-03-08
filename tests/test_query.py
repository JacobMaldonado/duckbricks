"""Tests for the Execution Environment (legacy compatibility)."""
import pytest

from app.services.ducklake import DuckLakeManager


def test_query_workspace_is_importable():
    """query_workspace should be importable."""
    from app.pages.query import query_workspace

    assert callable(query_workspace)


def test_execute_query_raises_when_not_initialized():
    """execute_query should raise when not initialized."""
    mgr = DuckLakeManager()
    with pytest.raises(RuntimeError, match="not initialized"):
        mgr.execute_query("SELECT 1")


def test_execute_query_typed_raises_when_not_initialized():
    """execute_query_typed should raise when not initialized."""
    mgr = DuckLakeManager()
    with pytest.raises(RuntimeError, match="not initialized"):
        mgr.execute_query_typed("SELECT 1")
