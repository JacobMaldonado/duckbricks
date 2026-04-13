"""DuckDB + DuckLake connection manager."""

import os
import threading

import duckdb

from app.config import CATALOG_PATH, DATA_PATH, DUCKLAKE_NAME


class MetastoreManager:
    """Manages the DuckDB connection with DuckLake metastore."""

    def __init__(self):
        self._lock = threading.Lock()
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._initialized = False

    def _ensure_data_path(self):
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
                f"(DATA_PATH '{DATA_PATH}', AUTOMATIC_MIGRATION TRUE)"
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
                if row[0] not in excluded and not row[0].startswith("__ducklake_metadata_")
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
        """Execute a SQL query and return results with column type info."""
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        with self._lock:
            try:
                result = self._conn.execute(sql)
                description = result.description
                if description:
                    columns = [{"name": desc[0], "type": str(desc[1])} for desc in description]
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

    def get_table_comment(self, catalog: str, schema: str, table: str) -> str | None:
        """Return the comment/description for a table, or None if not set."""
        with self._lock:
            try:
                result = self._conn.execute(
                    "SELECT comment FROM information_schema.tables "
                    "WHERE table_catalog = ? AND table_schema = ? AND table_name = ?",
                    [catalog, schema, table],
                ).fetchone()
                return result[0] if result else None
            except Exception:
                return None

    def get_view_definition(self, catalog: str, schema: str, view: str) -> str | None:
        """Return the SQL definition for a view, or None if not a view."""
        with self._lock:
            try:
                result = self._conn.execute(
                    "SELECT view_definition FROM information_schema.views "
                    "WHERE table_catalog = ? AND table_schema = ? AND table_name = ?",
                    [catalog, schema, view],
                ).fetchone()
                return result[0] if result else None
            except Exception:
                return None

    def get_table_history(self, catalog: str, schema: str, table: str) -> list[dict]:
        """Return DuckLake snapshot history for a table."""
        with self._lock:
            try:
                rows = self._conn.execute(
                    f"SELECT * FROM ducklake_snapshots('{catalog}') "
                    f"WHERE schema_name = '{schema}' AND table_name = '{table}' "
                    f"ORDER BY snapshot_id DESC"
                ).fetchall()
                desc = self._conn.description
                if not desc or not rows:
                    return []
                col_names = [d[0] for d in desc]
                return [dict(zip(col_names, row)) for row in rows]
            except Exception:
                return []

    def get_table_properties(self, catalog: str, schema: str, table: str) -> dict:
        """Return file-level properties: path, file count, total size."""
        with self._lock:
            props: dict = {
                "catalog": catalog,
                "schema": schema,
                "table": table,
                "catalog_path": CATALOG_PATH,
                "data_path": DATA_PATH,
                "file_count": None,
                "total_size_bytes": None,
            }
            try:
                rows = self._conn.execute(
                    f"SELECT path, file_size_bytes FROM ducklake_files('{catalog}') "
                    f"WHERE schema_name = '{schema}' AND table_name = '{table}'"
                ).fetchall()
                props["file_count"] = len(rows)
                props["total_size_bytes"] = sum(r[1] for r in rows if r[1] is not None)
            except Exception:
                pass
            return props

    def list_tables_in_schema_with_types(self, catalog: str, schema: str) -> list[dict]:
        """Return list of dicts with name and table_type (BASE TABLE or VIEW)."""
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")
        with self._lock:
            result = self._conn.execute(
                "SELECT table_name, table_type FROM information_schema.tables "
                "WHERE table_catalog = ? AND table_schema = ?",
                [catalog, schema],
            ).fetchall()
            return [{"name": row[0], "table_type": row[1]} for row in result]

    def list_columns(self, catalog: str, schema: str, table: str) -> list[dict]:
        """Return column names and data types for a specific table."""
        if not self._initialized:
            return []
        with self._lock:
            try:
                result = self._conn.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_catalog = ? AND table_schema = ? AND table_name = ? "
                    "ORDER BY ordinal_position",
                    [catalog, schema, table],
                ).fetchall()
                return [{"name": row[0], "type": row[1]} for row in result]
            except Exception:
                return []

    def search_tables(self, query: str) -> list[dict]:
        """Search tables and views by name across all catalogs."""
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT table_catalog, table_schema, table_name, table_type "
                    "FROM information_schema.tables "
                    "WHERE LOWER(table_name) LIKE LOWER(?)",
                    [f"%{query}%"],
                ).fetchall()
                return [
                    {
                        "catalog": row[0],
                        "schema": row[1],
                        "name": row[2],
                        "table_type": row[3],
                        "full_path": f"{row[0]}.{row[1]}.{row[2]}",
                    }
                    for row in rows
                ]
            except Exception:
                return []
