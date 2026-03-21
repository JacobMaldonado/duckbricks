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

    def create_table(
        self,
        catalog: str,
        schema: str,
        table_name: str,
        columns: list[dict],
        description: str | None = None,
    ) -> dict:
        """Create a new table with the given structure.

        Args:
            catalog: Catalog name
            schema: Schema name
            table_name: Table name (lowercase, alphanumeric, underscores)
            columns: List of column definitions, each dict with:
                - name: str (column name)
                - data_type: str (e.g., 'VARCHAR', 'INTEGER', 'TIMESTAMP')
                - is_nullable: bool (default True)
                - comment: str | None (optional column comment)
            description: Optional table description

        Returns:
            dict with:
                - success: bool
                - message: str (success message)
                - error: str | None (on failure)
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        # Validate table name
        import re
        if not re.match(r"^[a-z0-9_]+$", table_name):
            return {
                "success": False,
                "error": "Table name must contain only lowercase letters, numbers, and underscores",
            }

        # Validate columns
        if not columns or len(columns) == 0:
            return {
                "success": False,
                "error": "At least one column is required",
            }

        for col in columns:
            if not col.get("name"):
                return {
                    "success": False,
                    "error": "Column name is required",
                }
            if not re.match(r"^[a-z0-9_]+$", col["name"]):
                return {
                    "success": False,
                    "error": f"Column name '{col['name']}' must contain only lowercase letters, numbers, and underscores",
                }
            if not col.get("data_type"):
                return {
                    "success": False,
                    "error": f"Data type is required for column '{col['name']}'",
                }

        # Check if table already exists
        with self._lock:
            existing_tables = self._conn.execute(
                f"SELECT table_name FROM information_schema.tables "
                f"WHERE table_catalog = '{catalog}' "
                f"AND table_schema = '{schema}' "
                f"AND table_name = '{table_name}'"
            ).fetchall()

            if existing_tables:
                return {
                    "success": False,
                    "error": f"Table '{catalog}.{schema}.{table_name}' already exists",
                }

            # Build CREATE TABLE SQL
            column_defs = []
            for col in columns:
                col_name = col["name"]
                col_type = col["data_type"]
                is_nullable = col.get("is_nullable", True)
                nullable_clause = "" if is_nullable else " NOT NULL"
                column_defs.append(f"{col_name} {col_type}{nullable_clause}")

            columns_sql = ", ".join(column_defs)
            create_sql = f"CREATE TABLE {catalog}.{schema}.{table_name} ({columns_sql})"

            # Execute CREATE TABLE
            try:
                self._conn.execute(create_sql)
                return {
                    "success": True,
                    "message": f"Table '{catalog}.{schema}.{table_name}' created successfully",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to create table: {str(e)}",
                }


# Singleton
manager = DuckLakeManager()
