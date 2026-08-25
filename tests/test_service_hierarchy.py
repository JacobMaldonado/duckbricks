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
        f"(DATA_PATH '{data_path}', AUTOMATIC_MIGRATION TRUE)"
    )
    mgr._conn.execute("USE testcat")
    mgr._initialized = True

    # Create test schema and tables
    mgr._conn.execute("CREATE SCHEMA testcat.analytics")
    mgr._conn.execute("CREATE TABLE testcat.main.users (id INTEGER, name VARCHAR)")
    mgr._conn.execute("INSERT INTO testcat.main.users VALUES (1, 'Alice'), (2, 'Bob')")
    mgr._conn.execute("COMMENT ON TABLE testcat.main.users IS 'Application users'")
    mgr._conn.execute("COMMENT ON COLUMN testcat.main.users.name IS 'Display name'")
    mgr._conn.execute("CREATE VIEW testcat.main.user_names AS SELECT name FROM testcat.main.users")
    mgr._conn.execute("COMMENT ON VIEW testcat.main.user_names IS 'User names view'")
    mgr._conn.execute(
        "CREATE TABLE testcat.analytics.events (ts TIMESTAMP, event_type VARCHAR, value DOUBLE)"
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
    tables_main = initialized_manager.list_tables_in_schema("testcat", "main")
    assert "users" in tables_main

    tables_analytics = initialized_manager.list_tables_in_schema("testcat", "analytics")
    assert "events" in tables_analytics


def test_list_tables_in_schema_empty(initialized_manager):
    """Should return empty list for schema with no tables."""
    initialized_manager._conn.execute("CREATE SCHEMA testcat.empty_schema")
    tables = initialized_manager.list_tables_in_schema("testcat", "empty_schema")
    assert tables == []


def test_get_asset_type_distinguishes_tables_and_views(initialized_manager):
    assert initialized_manager.get_asset_type("testcat", "main", "users") == "BASE TABLE"
    assert initialized_manager.get_asset_type("testcat", "main", "user_names") == "VIEW"
    assert initialized_manager.get_asset_type("testcat", "main", "missing") is None


def test_get_table_comment_returns_table_and_view_descriptions(initialized_manager):
    assert initialized_manager.get_table_comment("testcat", "main", "users") == "Application users"
    assert (
        initialized_manager.get_table_comment("testcat", "main", "user_names") == "User names view"
    )


def test_list_columns_includes_nullability_and_comments(initialized_manager):
    columns = initialized_manager.list_columns("testcat", "main", "users")

    assert columns == [
        {
            "name": "id",
            "type": "INTEGER",
            "nullable": True,
            "description": None,
        },
        {
            "name": "name",
            "type": "VARCHAR",
            "nullable": True,
            "description": "Display name",
        },
    ]


def test_get_table_history_filters_snapshots_for_asset(initialized_manager):
    history = initialized_manager.get_table_history("testcat", "main", "users")

    assert history
    assert all("snapshot_id" in snapshot for snapshot in history)
    assert all("operation" in snapshot for snapshot in history)
    assert any("insert" in snapshot["operation"] for snapshot in history)


def test_get_table_properties_uses_current_ducklake_functions(initialized_manager):
    properties = initialized_manager.get_table_properties("testcat", "main", "users")

    assert properties["estimated_rows"] == 2
    assert properties["file_count"] is not None
    assert properties["total_size_bytes"] is not None
    assert properties["asset_uuid"]


def test_view_properties_have_no_physical_table_metrics(initialized_manager):
    properties = initialized_manager.get_table_properties("testcat", "main", "user_names")

    assert properties["estimated_rows"] is None
    assert properties["file_count"] is None
    assert properties["total_size_bytes"] is None
    assert properties["asset_uuid"]


def test_execute_query_typed_returns_types(initialized_manager):
    """execute_query_typed should return column type information."""
    result = initialized_manager.execute_query_typed("SELECT * FROM testcat.main.users")
    assert result["success"] is True
    assert len(result["columns"]) == 2
    assert result["columns"][0]["name"] == "id"
    assert "INT" in result["columns"][0]["type"].upper()
    assert result["columns"][1]["name"] == "name"
    assert "VARCHAR" in result["columns"][1]["type"].upper()
    assert result["row_count"] == 2


def test_execute_query_typed_error(initialized_manager):
    """execute_query_typed should return error on bad SQL."""
    result = initialized_manager.execute_query_typed("SELECT * FROM nonexistent_table")
    assert result["success"] is False
    assert result["error"] is not None


def test_execute_query_typed_ddl(initialized_manager):
    """execute_query_typed should handle DDL (no result set)."""
    result = initialized_manager.execute_query_typed("CREATE TABLE testcat.main.tmp_test (x INT)")
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
