"""DuckDB + DuckLake connection manager."""

import os
import threading

import duckdb

from app.config import CATALOG_PATH, DATA_PATH, DUCKLAKE_NAME


class DuckLakeManager:
    """Manages the DuckDB connection with DuckLake metastore."""

    def __init__(self):
        self._lock = threading.Lock()
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._initialized = False

    def _ensure_data_path(self):
        """Ensure the data directory exists."""
        os.makedirs(os.path.dirname(CATALOG_PATH), exist_ok=True)
        os.makedirs(DATA_PATH, exist_ok=True)

    def initialize(self) -> dict:
        """Initialize or attach the DuckLake metastore."""
        with self._lock:
            self._ensure_data_path()
            if self._conn is not None:
                self._conn.close()

            self._conn = duckdb.connect()
            self._conn.execute("INSTALL ducklake; LOAD ducklake;")
            self._conn.execute(
                f"ATTACH 'ducklake:{CATALOG_PATH}' AS {DUCKLAKE_NAME} "
                f"(DATA_PATH '{DATA_PATH}')"
            )
            self._conn.execute(f"USE {DUCKLAKE_NAME}")
            self._initialized = True
            return self.status()

    def status(self) -> dict:
        """Return metastore status."""
        return {
            "initialized": self._initialized,
            "catalog_path": CATALOG_PATH,
            "data_path": DATA_PATH,
            "ducklake_name": DUCKLAKE_NAME,
            "catalog_exists": os.path.exists(CATALOG_PATH),
        }

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def execute_query(self, sql: str) -> dict:
        """Execute a SQL query and return results."""
        if not self._initialized:
            raise RuntimeError("Metastore not initialized. Call POST /api/metastore/init first.")

        with self._lock:
            try:
                result = self._conn.execute(sql)
                description = result.description
                if description:
                    columns = [col[0] for col in description]
                    rows = result.fetchall()
                    return {
                        "success": True,
                        "columns": columns,
                        "rows": [list(row) for row in rows],
                        "row_count": len(rows),
                    }
                else:
                    return {
                        "success": True,
                        "columns": [],
                        "rows": [],
                        "row_count": 0,
                        "message": "Query executed successfully (no results).",
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }

    def list_tables(self) -> list[dict]:
        """List all tables in the DuckLake metastore."""
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        with self._lock:
            tables_result = self._conn.execute(
                f"SELECT table_name FROM information_schema.tables "
                f"WHERE table_catalog = '{DUCKLAKE_NAME}' AND table_schema = 'main'"
            ).fetchall()

            tables = []
            for (table_name,) in tables_result:
                col_info = self._conn.execute(
                    f"SELECT column_name, data_type FROM information_schema.columns "
                    f"WHERE table_catalog = '{DUCKLAKE_NAME}' AND table_schema = 'main' "
                    f"AND table_name = '{table_name}'"
                ).fetchall()

                try:
                    count_result = self._conn.execute(
                        f'SELECT COUNT(*) FROM {DUCKLAKE_NAME}.main."{table_name}"'
                    ).fetchone()
                    row_count = count_result[0] if count_result else 0
                except Exception:
                    row_count = -1

                tables.append(
                    {
                        "name": table_name,
                        "column_count": len(col_info),
                        "row_count": row_count,
                        "columns": [
                            {"column_name": col[0], "data_type": col[1]} for col in col_info
                        ],
                    }
                )

            return tables

    def list_catalogs(self) -> list[str]:
        """List all user-facing database catalogs (excluding system databases)."""
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        with self._lock:
            result = self._conn.execute("SHOW DATABASES").fetchall()
            excluded = {"memory", "system", "temp"}
            return [
                row[0]
                for row in result
                if row[0] not in excluded
                and not row[0].startswith("__ducklake_metadata_")
            ]

    def list_schemas(self, catalog: str) -> list[str]:
        """List schemas within a catalog."""
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        with self._lock:
            result = self._conn.execute(
                f"SELECT schema_name FROM information_schema.schemata "
                f"WHERE catalog_name = '{catalog}'"
            ).fetchall()
            return [row[0] for row in result]

    def list_tables_in_schema(self, catalog: str, schema: str) -> list[str]:
        """List table names in a specific catalog.schema."""
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        with self._lock:
            result = self._conn.execute(
                f"SELECT table_name FROM information_schema.tables "
                f"WHERE table_catalog = '{catalog}' "
                f"AND table_schema = '{schema}'"
            ).fetchall()
            return [row[0] for row in result]

    def execute_query_typed(self, sql: str) -> dict:
        """Execute a SQL query and return results with column type info.

        Returns dict with:
            - success: bool
            - columns: list of {"name": str, "type": str}
            - rows: list of lists
            - row_count: int
            - message: str | None (for DDL/non-result queries)
            - error: str | None (on failure)
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        with self._lock:
            try:
                result = self._conn.execute(sql)
                description = result.description
                if description:
                    columns = [
                        {"name": desc[0], "type": str(desc[1])}
                        for desc in description
                    ]
                    rows = result.fetchall()
                    return {
                        "success": True,
                        "columns": columns,
                        "rows": [list(row) for row in rows],
                        "row_count": len(rows),
                    }
                else:
                    return {
                        "success": True,
                        "columns": [],
                        "rows": [],
                        "row_count": 0,
                        "message": "Query executed successfully "
                        "(no results).",
                    }
            except Exception as e:
                return {
                    "success": False,
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "error": str(e),
                }

    def get_table(self, table_name: str) -> dict | None:
        """Get detailed info for a specific table."""
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        with self._lock:
            exists = self._conn.execute(
                f"SELECT table_name FROM information_schema.tables "
                f"WHERE table_catalog = '{DUCKLAKE_NAME}' AND table_schema = 'main' "
                f"AND table_name = '{table_name}'"
            ).fetchone()

            if not exists:
                return None

            col_info = self._conn.execute(
                f"SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                f"WHERE table_catalog = '{DUCKLAKE_NAME}' AND table_schema = 'main' "
                f"AND table_name = '{table_name}' ORDER BY ordinal_position"
            ).fetchall()

            try:
                count_result = self._conn.execute(
                    f'SELECT COUNT(*) FROM {DUCKLAKE_NAME}.main."{table_name}"'
                ).fetchone()
                row_count = count_result[0] if count_result else 0
            except Exception:
                row_count = -1

            return {
                "name": table_name,
                "column_count": len(col_info),
                "row_count": row_count,
                "columns": [
                    {
                        "column_name": col[0],
                        "data_type": col[1],
                        "is_nullable": col[2],
                    }
                    for col in col_info
                ],
            }

    def get_table_details(self, catalog: str, schema: str, table: str) -> dict:
        """Get detailed information about a specific table.
        
        Returns:
            dict with keys: name, row_count, column_count, size_bytes (estimated)
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")
        
        with self._lock:
            # Get column count
            col_count_result = self._conn.execute(
                f"SELECT COUNT(*) FROM information_schema.columns "
                f"WHERE table_catalog = '{catalog}' "
                f"AND table_schema = '{schema}' "
                f"AND table_name = '{table}'"
            ).fetchone()
            
            column_count = col_count_result[0] if col_count_result else 0
            
            # Get row count (try to query the actual table)
            try:
                row_count_result = self._conn.execute(
                    f'SELECT COUNT(*) FROM "{catalog}"."{schema}"."{table}"'
                ).fetchone()
                row_count = row_count_result[0] if row_count_result else 0
            except Exception:
                row_count = 0
            
            # Estimate size (this is approximate - DuckDB doesn't expose file sizes directly)
            # We'll return -1 to indicate unavailable for now
            size_bytes = -1
            
            return {
                "name": table,
                "row_count": row_count,
                "column_count": column_count,
                "size_bytes": size_bytes,
            }

    def get_schema_table_stats(self, catalog: str, schema: str) -> dict:
        """Get aggregate statistics for all tables in a schema.
        
        Returns:
            dict with keys: table_count, total_rows
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")
        
        with self._lock:
            # Count tables
            table_count_result = self._conn.execute(
                f"SELECT COUNT(*) FROM information_schema.tables "
                f"WHERE table_catalog = '{catalog}' AND table_schema = '{schema}'"
            ).fetchone()
            
            table_count = table_count_result[0] if table_count_result else 0
            
            # Get table names directly within the lock (not via list_tables_in_schema to avoid deadlock)
            table_names_result = self._conn.execute(
                f"SELECT table_name FROM information_schema.tables "
                f"WHERE table_catalog = '{catalog}' "
                f"AND table_schema = '{schema}'"
            ).fetchall()
            table_names = [row[0] for row in table_names_result]
            
            # Calculate total rows across all tables (note: this can be slow for many tables)
            total_rows = 0
            
            for table in table_names:
                try:
                    row_result = self._conn.execute(
                        f'SELECT COUNT(*) FROM "{catalog}"."{schema}"."{table}"'
                    ).fetchone()
                    if row_result:
                        total_rows += row_result[0]
                except Exception:
                    # Skip tables that can't be counted
                    pass
            
            return {
                "table_count": table_count,
                "total_rows": total_rows,
            }


# Singleton
manager = DuckLakeManager()
