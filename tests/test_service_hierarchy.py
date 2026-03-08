"""Tests for DuckLakeManager hierarchy and typed query methods."""

import os
import shutil
import tempfile
import threading

import duckdb
import pytest


@pytest.fixture
def initialized_manager():
    """Create a DuckLakeManager with a real DuckLake catalog for testing."""
    from app.services.ducklake import DuckLakeManager

    tmpdir = tempfile.mkdtemp()
    catalog_path = os.path.join(tmpdir, "test.ducklake")
    data_path = os.path.join(tmpdir, "data")
    os.makedirs(data_path, exist_ok=True)

    mgr = DuckLakeManager.__new__(DuckLakeManager)
    mgr._lock = threading.Lock()
    mgr._conn = duckdb.connect()
    mgr._conn.execute("INSTALL ducklake; LOAD ducklake;")
    mgr._conn.execute(
        f"ATTACH 'ducklake:{catalog_path}' AS testcat "
        f"(DATA_PATH '{data_path}')"
    )
    mgr._conn.execute("USE testcat")
    mgr._initialized = True

    # Create test schema and tables
    mgr._conn.execute("CREATE SCHEMA testcat.analytics")
    mgr._conn.execute(
        "CREATE TABLE testcat.main.users (id INTEGER, name VARCHAR)"
    )
    mgr._conn.execute(
        "INSERT INTO testcat.main.users VALUES (1, 'Alice'), (2, 'Bob')"
    )
    mgr._conn.execute(
        "CREATE TABLE testcat.analytics.events "
        "(ts TIMESTAMP, event_type VARCHAR, value DOUBLE)"
    )

    yield mgr

    mgr._conn.close()
    shutil.rmtree(tmpdir)


def test_list_catalogs(initialized_manager):
    """Should return the attached DuckLake catalog."""
    catalogs = initialized_manager.list_catalogs()
    assert "testcat" in catalogs
    assert "memory" not in catalogs
    assert "system" not in catalogs
    assert "temp" not in catalogs
    for c in catalogs:
        assert not c.startswith("__ducklake_metadata_")


def test_list_schemas(initialized_manager):
    """Should return schemas for a catalog."""
    schemas = initialized_manager.list_schemas("testcat")
    assert "main" in schemas
    assert "analytics" in schemas


def test_list_tables_in_schema(initialized_manager):
    """Should return tables in a specific schema."""
    tables_main = initialized_manager.list_tables_in_schema(
        "testcat", "main"
    )
    assert "users" in tables_main

    tables_analytics = initialized_manager.list_tables_in_schema(
        "testcat", "analytics"
    )
    assert "events" in tables_analytics


def test_list_tables_in_schema_empty(initialized_manager):
    """Should return empty list for schema with no tables."""
    initialized_manager._conn.execute(
        "CREATE SCHEMA testcat.empty_schema"
    )
    tables = initialized_manager.list_tables_in_schema(
        "testcat", "empty_schema"
    )
    assert tables == []


def test_execute_query_typed_returns_types(initialized_manager):
    """execute_query_typed should return column type information."""
    result = initialized_manager.execute_query_typed(
        "SELECT * FROM testcat.main.users"
    )
    assert result["success"] is True
    assert len(result["columns"]) == 2
    assert result["columns"][0]["name"] == "id"
    assert "INT" in result["columns"][0]["type"].upper()
    assert result["columns"][1]["name"] == "name"
    assert "VARCHAR" in result["columns"][1]["type"].upper()
    assert result["row_count"] == 2


def test_execute_query_typed_error(initialized_manager):
    """execute_query_typed should return error on bad SQL."""
    result = initialized_manager.execute_query_typed(
        "SELECT * FROM nonexistent_table"
    )
    assert result["success"] is False
    assert result["error"] is not None


def test_execute_query_typed_ddl(initialized_manager):
    """execute_query_typed should handle DDL (no result set)."""
    result = initialized_manager.execute_query_typed(
        "CREATE TABLE testcat.main.tmp_test (x INT)"
    )
    assert result["success"] is True


def test_list_catalogs_not_initialized():
    """Should raise RuntimeError when not initialized."""
    from app.services.ducklake import DuckLakeManager

    mgr = DuckLakeManager()
    with pytest.raises(RuntimeError, match="not initialized"):
        mgr.list_catalogs()


def test_list_schemas_not_initialized():
    """Should raise RuntimeError when not initialized."""
    from app.services.ducklake import DuckLakeManager

    mgr = DuckLakeManager()
    with pytest.raises(RuntimeError, match="not initialized"):
        mgr.list_schemas("any")


def test_list_tables_in_schema_not_initialized():
    """Should raise RuntimeError when not initialized."""
    from app.services.ducklake import DuckLakeManager

    mgr = DuckLakeManager()
    with pytest.raises(RuntimeError, match="not initialized"):
        mgr.list_tables_in_schema("any", "any")


def test_execute_query_typed_not_initialized():
    """Should raise RuntimeError when not initialized."""
    from app.services.ducklake import DuckLakeManager

    mgr = DuckLakeManager()
    with pytest.raises(RuntimeError, match="not initialized"):
        mgr.execute_query_typed("SELECT 1")
