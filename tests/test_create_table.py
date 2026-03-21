"""Tests for create_table functionality."""

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

    # Create test schema
    mgr._conn.execute("CREATE SCHEMA testcat.analytics")

    yield mgr

    mgr._conn.close()
    shutil.rmtree(tmpdir)


def test_create_table_success(initialized_manager):
    """Should create a table with valid column definitions."""
    result = initialized_manager.create_table(
        catalog="testcat",
        schema="main",
        table_name="users",
        columns=[
            {"name": "id", "data_type": "BIGINT", "is_nullable": False},
            {"name": "name", "data_type": "VARCHAR", "is_nullable": False},
            {"name": "email", "data_type": "VARCHAR", "is_nullable": True},
            {"name": "created_at", "data_type": "TIMESTAMP", "is_nullable": False},
        ],
        description="User accounts table",
    )

    assert result["success"] is True
    assert "created successfully" in result["message"]

    # Verify table exists
    tables = initialized_manager.list_tables_in_schema("testcat", "main")
    assert "users" in tables

    # Verify table structure using information_schema
    col_info = initialized_manager._conn.execute(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_catalog = 'testcat' AND table_schema = 'main' "
        "AND table_name = 'users' ORDER BY ordinal_position"
    ).fetchall()
    
    assert len(col_info) == 4
    assert col_info[0][0] == "id"
    assert col_info[0][2] == "NO"
    assert col_info[2][2] == "YES"


def test_create_table_invalid_name(initialized_manager):
    """Should reject table names with invalid characters."""
    result = initialized_manager.create_table(
        catalog="testcat",
        schema="main",
        table_name="Invalid-Table",
        columns=[{"name": "id", "data_type": "INTEGER", "is_nullable": False}],
    )

    assert result["success"] is False
    assert "lowercase letters, numbers, and underscores" in result["error"]


def test_create_table_invalid_column_name(initialized_manager):
    """Should reject column names with invalid characters."""
    result = initialized_manager.create_table(
        catalog="testcat",
        schema="main",
        table_name="valid_table",
        columns=[{"name": "Invalid-Column", "data_type": "INTEGER", "is_nullable": False}],
    )

    assert result["success"] is False
    assert "lowercase letters, numbers, and underscores" in result["error"]


def test_create_table_no_columns(initialized_manager):
    """Should reject table creation with no columns."""
    result = initialized_manager.create_table(
        catalog="testcat",
        schema="main",
        table_name="empty_table",
        columns=[],
    )

    assert result["success"] is False
    assert "At least one column is required" in result["error"]


def test_create_table_missing_column_name(initialized_manager):
    """Should reject columns without names."""
    result = initialized_manager.create_table(
        catalog="testcat",
        schema="main",
        table_name="bad_table",
        columns=[{"data_type": "INTEGER", "is_nullable": False}],
    )

    assert result["success"] is False
    assert "Column name is required" in result["error"]


def test_create_table_missing_data_type(initialized_manager):
    """Should reject columns without data types."""
    result = initialized_manager.create_table(
        catalog="testcat",
        schema="main",
        table_name="bad_table",
        columns=[{"name": "col1", "is_nullable": False}],
    )

    assert result["success"] is False
    assert "Data type is required" in result["error"]


def test_create_table_duplicate(initialized_manager):
    """Should reject creating a table that already exists."""
    # Create table first time
    result1 = initialized_manager.create_table(
        catalog="testcat",
        schema="main",
        table_name="duplicate_test",
        columns=[{"name": "id", "data_type": "INTEGER", "is_nullable": False}],
    )
    assert result1["success"] is True

    # Try to create again
    result2 = initialized_manager.create_table(
        catalog="testcat",
        schema="main",
        table_name="duplicate_test",
        columns=[{"name": "id", "data_type": "INTEGER", "is_nullable": False}],
    )

    assert result2["success"] is False
    assert "already exists" in result2["error"]


def test_create_table_in_custom_schema(initialized_manager):
    """Should create table in a non-main schema."""
    result = initialized_manager.create_table(
        catalog="testcat",
        schema="analytics",
        table_name="events",
        columns=[
            {"name": "event_id", "data_type": "BIGINT", "is_nullable": False},
            {"name": "event_type", "data_type": "VARCHAR", "is_nullable": False},
            {"name": "timestamp", "data_type": "TIMESTAMP", "is_nullable": False},
        ],
    )

    assert result["success"] is True

    # Verify table exists in analytics schema
    tables = initialized_manager.list_tables_in_schema("testcat", "analytics")
    assert "events" in tables


def test_create_table_not_initialized():
    """Should raise RuntimeError when not initialized."""
    from app.services.ducklake import DuckLakeManager

    mgr = DuckLakeManager()
    with pytest.raises(RuntimeError, match="not initialized"):
        mgr.create_table(
            catalog="any",
            schema="any",
            table_name="test",
            columns=[{"name": "id", "data_type": "INTEGER", "is_nullable": False}],
        )


def test_create_table_with_various_types(initialized_manager):
    """Should support creating tables with various column types."""
    result = initialized_manager.create_table(
        catalog="testcat",
        schema="main",
        table_name="multi_type_table",
        columns=[
            {"name": "col_varchar", "data_type": "VARCHAR", "is_nullable": True},
            {"name": "col_integer", "data_type": "INTEGER", "is_nullable": True},
            {"name": "col_bigint", "data_type": "BIGINT", "is_nullable": True},
            {"name": "col_double", "data_type": "DOUBLE", "is_nullable": True},
            {"name": "col_boolean", "data_type": "BOOLEAN", "is_nullable": True},
            {"name": "col_date", "data_type": "DATE", "is_nullable": True},
            {"name": "col_timestamp", "data_type": "TIMESTAMP", "is_nullable": True},
        ],
    )

    assert result["success"] is True

    # Verify table structure using information_schema
    col_info = initialized_manager._conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_catalog = 'testcat' AND table_schema = 'main' "
        "AND table_name = 'multi_type_table' ORDER BY ordinal_position"
    ).fetchall()
    
    assert len(col_info) == 7
