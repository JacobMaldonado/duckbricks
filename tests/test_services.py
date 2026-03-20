"""Tests for DuckBricks services."""

import tempfile
from pathlib import Path

import pytest

from app.services.ducklake import DuckLakeManager


def test_ducklake_manager_can_be_instantiated():
    """DuckLakeManager should instantiate without errors."""
    manager = DuckLakeManager()
    assert manager is not None
    assert manager.is_initialized is False


def test_ducklake_manager_status(ducklake_manager):
    """DuckLakeManager.status() should return expected keys."""
    status = ducklake_manager.status()
    assert "initialized" in status
    assert "catalog_path" in status
    assert "data_path" in status
    assert "ducklake_name" in status
    assert status["initialized"] is False


def test_get_table_details(monkeypatch):
    """Test getting detailed information about a specific table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("DUCKBRICKS_CATALOG_PATH", str(Path(tmpdir) / "metastore.ducklake"))
        monkeypatch.setenv("DUCKBRICKS_DATA_PATH", str(Path(tmpdir) / "parquet"))
        monkeypatch.setenv("DUCKBRICKS_DUCKLAKE_NAME", "test_catalog")
        
        import importlib
        import app.config
        importlib.reload(app.config)
        from app.services import ducklake
        importlib.reload(ducklake)
        
        manager = ducklake.manager
        manager.initialize()
        
        # Create a test schema and table with data
        manager.execute_query("CREATE SCHEMA test_schema")
        manager.execute_query("CREATE TABLE test_schema.users (id INTEGER, name VARCHAR, email VARCHAR)")
        manager.execute_query("INSERT INTO test_schema.users VALUES (1, 'Alice', 'alice@example.com'), (2, 'Bob', 'bob@example.com')")
        
        # Get table details
        details = manager.get_table_details("test_catalog", "test_schema", "users")
        
        assert details["name"] == "users"
        assert details["row_count"] == 2
        assert details["column_count"] == 3
        assert details["size_bytes"] == -1  # Not available in DuckDB


def test_get_table_details_empty_table(monkeypatch):
    """Test getting details for an empty table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("DUCKBRICKS_CATALOG_PATH", str(Path(tmpdir) / "metastore.ducklake"))
        monkeypatch.setenv("DUCKBRICKS_DATA_PATH", str(Path(tmpdir) / "parquet"))
        monkeypatch.setenv("DUCKBRICKS_DUCKLAKE_NAME", "test_catalog")
        
        import importlib
        import app.config
        importlib.reload(app.config)
        from app.services import ducklake
        importlib.reload(ducklake)
        
        manager = ducklake.manager
        manager.initialize()
        
        # Create empty table
        manager.execute_query("CREATE SCHEMA test_schema")
        manager.execute_query("CREATE TABLE test_schema.empty (id INTEGER)")
        
        details = manager.get_table_details("test_catalog", "test_schema", "empty")
        
        assert details["name"] == "empty"
        assert details["row_count"] == 0
        assert details["column_count"] == 1


def test_get_schema_table_stats(monkeypatch):
    """Test getting aggregate statistics for tables in a schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("DUCKBRICKS_CATALOG_PATH", str(Path(tmpdir) / "metastore.ducklake"))
        monkeypatch.setenv("DUCKBRICKS_DATA_PATH", str(Path(tmpdir) / "parquet"))
        monkeypatch.setenv("DUCKBRICKS_DUCKLAKE_NAME", "test_catalog")
        
        import importlib
        import app.config
        importlib.reload(app.config)
        from app.services import ducklake
        importlib.reload(ducklake)
        
        manager = ducklake.manager
        manager.initialize()
        
        # Create test schema with multiple tables
        manager.execute_query("CREATE SCHEMA test_schema")
        manager.execute_query("CREATE TABLE test_schema.table1 (id INTEGER)")
        manager.execute_query("INSERT INTO test_schema.table1 VALUES (1), (2), (3)")
        manager.execute_query("CREATE TABLE test_schema.table2 (id INTEGER)")
        manager.execute_query("INSERT INTO test_schema.table2 VALUES (1), (2)")
        
        stats = manager.get_schema_table_stats("test_catalog", "test_schema")
        
        assert stats["table_count"] == 2
        assert stats["total_rows"] == 5


def test_get_table_details_not_initialized():
    """Test that get_table_details raises error when not initialized."""
    manager = DuckLakeManager()
    
    with pytest.raises(RuntimeError, match="Metastore not initialized"):
        manager.get_table_details("catalog", "schema", "table")


def test_get_schema_table_stats_not_initialized():
    """Test that get_schema_table_stats raises error when not initialized."""
    manager = DuckLakeManager()
    
    with pytest.raises(RuntimeError, match="Metastore not initialized"):
        manager.get_schema_table_stats("catalog", "schema")
