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

                tables.append({
                    "name": table_name,
                    "column_count": len(col_info),
                    "row_count": row_count,
                    "columns": [
                        {"column_name": col[0], "data_type": col[1]}
                        for col in col_info
                    ],
                })

            return tables

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


# Singleton
manager = DuckLakeManager()
