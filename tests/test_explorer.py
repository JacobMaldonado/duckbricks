"""Tests for the Metastore Explorer."""
import pytest

from app.services.ducklake import DuckLakeManager


def test_explorer_page_is_importable():
    """explorer_page should be importable."""
    from app.pages.explorer import explorer_page

    assert callable(explorer_page)


def test_explorer_handles_uninitialized_manager():
    """Explorer should handle uninitialized metastore."""
    mgr = DuckLakeManager()
    assert mgr.is_initialized is False


def test_explorer_list_tables_empty_when_not_initialized():
    """list_tables should raise when not initialized."""
    mgr = DuckLakeManager()
    with pytest.raises(RuntimeError, match="not initialized"):
        mgr.list_tables()


def test_explorer_get_table_raises_when_not_initialized():
    """get_table should raise when not initialized."""
    mgr = DuckLakeManager()
    with pytest.raises(RuntimeError, match="not initialized"):
        mgr.get_table("some_table")
