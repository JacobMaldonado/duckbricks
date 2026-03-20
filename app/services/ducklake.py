"""DuckDB + DuckLake connection manager."""

import os
import threading

import duckdb

from app.config import CATALOG_PATH, DATA_PATH, DUCKLAKE_NAME


class DuckLakeManager:
    """Manages the DuckDB connection with DuckLake metastore."""

    def __init__(self):
        self._lock = threading.RLock()  # Use RLock for reentrant locking
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

    def get_catalog_details(self, catalog: str) -> dict:
        """Get detailed information about a catalog.

        Args:
            catalog: Catalog name

        Returns:
            dict with catalog metadata including schema count
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        with self._lock:
            try:
                # Get schema count
                schemas = self.list_schemas(catalog)
                schema_count = len(schemas)

                # Get total table count across all schemas
                table_count = 0
                for schema in schemas:
                    tables = self.list_tables_in_schema(catalog, schema)
                    table_count += len(tables)

                return {
                    "name": catalog,
                    "schema_count": schema_count,
                    "table_count": table_count,
                }
            except Exception as e:
                return {
                    "name": catalog,
                    "schema_count": 0,
                    "table_count": 0,
                    "error": str(e)
                }

    def get_metastore_stats(self) -> dict:
        """Get overall metastore statistics.

        Returns:
            dict with total counts of catalogs, schemas, and tables
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        catalogs = self.list_catalogs()
        total_schemas = 0
        total_tables = 0

        for catalog in catalogs:
            details = self.get_catalog_details(catalog)
            total_schemas += details.get("schema_count", 0)
            total_tables += details.get("table_count", 0)

        return {
            "total_catalogs": len(catalogs),
            "total_schemas": total_schemas,
            "total_tables": total_tables
        }

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

    def create_schema(self, catalog: str, name: str, description: str = "") -> dict:
        """Create a new schema within a catalog.

        Args:
            catalog: Catalog name where the schema will be created
            name: Schema name (lowercase, alphanumeric, underscores only)
            description: Optional schema description (for future use)

        Returns:
            dict with success status and message/error
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        # Validate schema name
        if not name or not name.replace("_", "").isalnum() or not name.islower():
            return {
                "success": False,
                "error": "Schema name must be lowercase alphanumeric with underscores only"
            }

        with self._lock:
            try:
                # Check if catalog exists
                catalogs = self._conn.execute("SHOW DATABASES").fetchall()
                if not any(row[0] == catalog for row in catalogs):
                    return {
                        "success": False,
                        "error": f"Catalog '{catalog}' does not exist"
                    }

                # Check if schema already exists
                existing_schemas = self._conn.execute(
                    f"SELECT schema_name FROM information_schema.schemata "
                    f"WHERE catalog_name = '{catalog}'"
                ).fetchall()
                if any(row[0] == name for row in existing_schemas):
                    return {
                        "success": False,
                        "error": f"Schema '{name}' already exists in catalog '{catalog}'"
                    }

                # Create the schema
                self._conn.execute(f"CREATE SCHEMA {catalog}.{name}")

                return {
                    "success": True,
                    "message": f"Schema '{name}' created successfully in catalog '{catalog}'"
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }

    def create_catalog(self, name: str, description: str = "", storage_path: str = "") -> dict:
        """Create a new catalog in DuckLake.

        Args:
            name: Catalog name (lowercase, alphanumeric, underscores only)
            description: Optional catalog description (metadata only, for future use)
            storage_path: Optional custom storage location (defaults to DATA_PATH/<catalog>)

        Returns:
            dict with success status and message/error
        """
        if not self._initialized:
            raise RuntimeError("Metastore not initialized.")

        # Validate catalog name
        if not name or not name.replace("_", "").isalnum() or not name.islower():
            return {
                "success": False,
                "error": "Catalog name must be lowercase alphanumeric with underscores only"
            }

        with self._lock:
            try:
                # Check if catalog already exists
                existing = self._conn.execute("SHOW DATABASES").fetchall()
                if any(row[0] == name for row in existing):
                    return {
                        "success": False,
                        "error": f"Catalog '{name}' already exists"
                    }

                # Create a new DuckLake catalog by attaching a new catalog file
                # Determine storage paths
                catalog_dir = os.path.dirname(CATALOG_PATH)
                catalog_file = os.path.join(catalog_dir, f"{name}.ducklake")
                
                if storage_path:
                    data_path = storage_path
                else:
                    data_path = os.path.join(DATA_PATH, name)
                
                # Ensure directories exist
                os.makedirs(catalog_dir, exist_ok=True)
                os.makedirs(data_path, exist_ok=True)
                
                # Attach the new DuckLake catalog
                self._conn.execute(
                    f"ATTACH 'ducklake:{catalog_file}' AS {name} "
                    f"(DATA_PATH '{data_path}')"
                )

                return {
                    "success": True,
                    "message": f"Catalog '{name}' created successfully"
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }


# Singleton
manager = DuckLakeManager()
