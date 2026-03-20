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


def test_get_schema_details(monkeypatch):
    """Test getting schema details including table count."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set environment variables before importing config
        monkeypatch.setenv("DUCKBRICKS_CATALOG_PATH", str(Path(tmpdir) / "metastore.ducklake"))
        monkeypatch.setenv("DUCKBRICKS_DATA_PATH", str(Path(tmpdir) / "parquet"))
        monkeypatch.setenv("DUCKBRICKS_DUCKLAKE_NAME", "test_catalog")
        
        # Force reload of config module to pick up new env vars
        import importlib
        import app.config
        importlib.reload(app.config)
        
        # Now import manager with fresh config
        from app.services import ducklake
        importlib.reload(ducklake)
        
        manager = ducklake.manager
        manager.initialize()
        
        # Create a test schema and tables
        manager.execute_query("CREATE SCHEMA test_schema")
        manager.execute_query("CREATE TABLE test_schema.table1 (id INTEGER, name VARCHAR)")
        manager.execute_query("CREATE TABLE test_schema.table2 (id INTEGER)")
        
        # Get schema details
        details = manager.get_schema_details("test_catalog", "test_schema")
        
        assert details["name"] == "test_schema"
        assert details["table_count"] == 2


def test_get_schema_details_empty(monkeypatch):
    """Test getting schema details for schema with no tables."""
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
        
        # Create empty schema
        manager.execute_query("CREATE SCHEMA empty_schema")
        
        details = manager.get_schema_details("test_catalog", "empty_schema")
        
        assert details["name"] == "empty_schema"
        assert details["table_count"] == 0


def test_get_catalog_stats(monkeypatch):
    """Test getting catalog-level statistics."""
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
        
        # Create test schemas and tables
        manager.execute_query("CREATE SCHEMA schema1")
        manager.execute_query("CREATE SCHEMA schema2")
        manager.execute_query("CREATE TABLE schema1.table1 (id INTEGER)")
        manager.execute_query("CREATE TABLE schema1.table2 (id INTEGER)")
        manager.execute_query("CREATE TABLE schema2.table3 (id INTEGER)")
        
        stats = manager.get_catalog_stats("test_catalog")
        
        # Should have 2 schemas + main (default)
        assert stats["schema_count"] >= 2
        # Should have 3 tables total
        assert stats["total_tables"] == 3


def test_get_schema_details_not_initialized():
    """Test that get_schema_details raises error when not initialized."""
    manager = DuckLakeManager()
    
    with pytest.raises(RuntimeError, match="Metastore not initialized"):
        manager.get_schema_details("test_catalog", "test_schema")


def test_get_catalog_stats_not_initialized():
    """Test that get_catalog_stats raises error when not initialized."""
    manager = DuckLakeManager()
    
    with pytest.raises(RuntimeError, match="Metastore not initialized"):
        manager.get_catalog_stats("test_catalog")
