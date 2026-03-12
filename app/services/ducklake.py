"""DuckDB + DuckLake connection manager."""

import csv
import io
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

    def export_results_to_csv(self, sql: str) -> bytes:
        """Execute query and return results as CSV bytes.
        
        Uses streaming to handle large result sets efficiently.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            CSV data as bytes
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        with self._lock:
            result = self._conn.execute(sql)

            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            columns = [desc[0] for desc in result.description]
            writer.writerow(columns)

            # Write rows (fetch in batches for large results)
            batch_size = 10000
            while True:
                rows = result.fetchmany(batch_size)
                if not rows:
                    break
                for row in rows:
                    writer.writerow(row)

            # Convert to bytes
            return output.getvalue().encode('utf-8')

    def get_table_details(self, full_table_name: str) -> dict:
        """Get detailed table information including partitioning, constraints, stats.
        
        Args:
            full_table_name: catalog.schema.table
            
        Returns:
            {
                "partitions": [...],
                "constraints": [...],
                "file_count": int,
                "table_size_bytes": int,
                "row_count": int,
                "last_modified": str (ISO timestamp) or None
            }
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        parts = full_table_name.split(".")
        if len(parts) != 3:
            raise ValueError(
                "Invalid table name format. Expected: catalog.schema.table"
            )

        catalog, schema, table = parts

        with self._lock:
            # Get row count
            try:
                count_result = self._conn.execute(
                    f'SELECT COUNT(*) FROM "{catalog}"."{schema}"."{table}"'
                ).fetchone()
                row_count = count_result[0] if count_result else 0
            except Exception:
                row_count = -1

            # Get constraints (simplified - DuckDB info_schema support)
            constraints = []
            try:
                constraint_info = self._conn.execute(
                    f"""
                    SELECT constraint_type, constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_catalog = '{catalog}'
                      AND table_schema = '{schema}'
                      AND table_name = '{table}'
                    """
                ).fetchall()
                constraints = [
                    {
                        "type": row[0],
                        "name": row[1],
                        "definition": f"{row[0]} constraint"
                    }
                    for row in constraint_info
                ]
            except Exception:
                # Not all databases support this
                pass

            # Placeholder values for features not yet implemented
            return {
                "partitions": [],  # TODO: Query DuckLake partitioning info
                "constraints": constraints,
                "file_count": 0,    # TODO: Query DuckLake file metadata
                "table_size_bytes": 0,  # TODO: Sum file sizes
                "row_count": row_count,
                "last_modified": None  # TODO: Query last write timestamp
            }

    def get_table_history(self, full_table_name: str) -> list[dict]:
        """Get time travel history for a table (DuckLake versions).
        
        Returns:
            [
                {
                    "version_id": str,
                    "timestamp": str (ISO),
                    "is_current": bool
                },
                ...
            ]
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        # Note: This depends on DuckLake's versioning implementation
        # DuckLake uses Iceberg-like versioning
        # This is a placeholder until DuckLake exposes version history

        # TODO: Query DuckLake version history when API is available
        return []

    def search_tables(self, query: str) -> list[dict]:
        """Search for tables matching query string.
        
        Returns list of dicts with:
            - full_name: str (catalog.schema.table)
            - catalog: str
            - schema: str
            - table: str
            - column_count: int
        
        Args:
            query: Search string to match against table names
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        if not query or len(query) < 1:
            return []

        with self._lock:
            # Use parameterized query to avoid SQL injection
            # and search across all catalogs
            sql = """
                SELECT 
                    table_catalog || '.' || table_schema || '.' || table_name as full_name,
                    table_catalog,
                    table_schema,
                    table_name,
                    (SELECT COUNT(*) FROM information_schema.columns c 
                     WHERE c.table_catalog = t.table_catalog 
                       AND c.table_schema = t.table_schema 
                       AND c.table_name = t.table_name) as column_count
                FROM information_schema.tables t
                WHERE LOWER(table_name) LIKE LOWER(?)
                ORDER BY table_name
                LIMIT 10
            """

            try:
                result = self._conn.execute(
                    sql, [f"%{query}%"]
                ).fetchall()

                return [
                    {
                        "full_name": row[0],
                        "catalog": row[1],
                        "schema": row[2],
                        "table": row[3],
                        "column_count": row[4]
                    }
                    for row in result
                ]
            except Exception:
                return []


# Singleton
manager = DuckLakeManager()
