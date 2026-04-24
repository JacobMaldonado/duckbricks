"""DuckBricks workspace utilities — importable in any Marimo notebook.

This module is deployed to /data/.duckbricks/ at application startup and
exposed via PYTHONPATH so notebooks can connect to the DuckLake catalog
without managing credentials themselves.

Example usage in a Marimo cell:
    from duckbricks_utils import connect

    conn = connect()
    result = conn.execute("SELECT * FROM my_table LIMIT 10").df()
"""

from __future__ import annotations

import os

import duckdb


def _pg_dsn() -> str:
    host = os.getenv("DUCKLAKE_PG_HOST", "localhost")
    port = os.getenv("DUCKLAKE_PG_PORT", "5432")
    database = os.getenv("DUCKLAKE_PG_DATABASE", "duckbricks")
    user = os.getenv("DUCKLAKE_PG_USER", "duckbricks")
    password = os.getenv("DUCKLAKE_PG_PASSWORD", "duckbricks")
    return f"host={host} port={port} dbname={database} user={user} password={password}"


def catalog_name() -> str:
    """Return the configured DuckLake catalog name."""
    return os.getenv("DUCKBRICKS_DUCKLAKE_NAME", "duckbricks")


def data_path() -> str:
    """Return the configured Parquet data storage path."""
    return os.getenv("DUCKBRICKS_DATA_PATH", "/data/parquet/")


def connect(override_data_path: str | None = None) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection with the DuckLake catalog attached.

    The catalog backend is PostgreSQL, configured via DUCKLAKE_PG_* environment
    variables that are injected into the Marimo container automatically.

    Args:
        override_data_path: Optional path override for the Parquet data directory.
            Defaults to the DUCKBRICKS_DATA_PATH environment variable.

    Returns:
        An open DuckDB connection with the DuckLake catalog set as default.
    """
    storage_path = override_data_path or data_path()
    name = catalog_name()
    dsn = _pg_dsn()

    conn = duckdb.connect()
    conn.execute("INSTALL ducklake; LOAD ducklake;")
    conn.execute("INSTALL postgres; LOAD postgres;")
    conn.execute(
        f"ATTACH 'ducklake:postgres:{dsn}' AS {name} "
        f"(DATA_PATH '{storage_path}', AUTOMATIC_MIGRATION TRUE)"
    )
    conn.execute(f"USE {name}")
    return conn
