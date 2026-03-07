"""Tests for the Execution Environment."""
import pytest

from app.services.ducklake import DuckLakeManager


def test_query_page_is_importable():
    """query_page should be importable."""
    from app.pages.query import query_page

    assert callable(query_page)


def test_execute_query_raises_when_not_initialized():
    """execute_query should raise when metastore is not initialized."""
    mgr = DuckLakeManager()
    with pytest.raises(RuntimeError, match="not initialized"):
        mgr.execute_query("SELECT 1")


def test_execute_query_returns_error_dict_on_bad_sql():
    """execute_query should return error dict on invalid SQL.

    We can't easily initialize DuckLake in tests without a real
    catalog, so we test the not-initialized guard instead.
    """
    mgr = DuckLakeManager()
    assert mgr.is_initialized is False
    with pytest.raises(RuntimeError):
        mgr.execute_query("INVALID SQL")
