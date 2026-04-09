"""SQL query execution engine backed by a DuckDB connection."""

from app.services.metastore.ducklake_manager import MetastoreManager


class QueryEngine:
    """Executes SQL queries against the DuckLake catalog."""

    def __init__(self, metastore: MetastoreManager) -> None:
        self._metastore = metastore

    def execute(self, sql: str) -> dict:
        """Execute SQL and return plain columns/rows result."""
        return self._metastore.execute_query(sql)

    def execute_typed(self, sql: str) -> dict:
        """Execute SQL and return typed column metadata with rows."""
        return self._metastore.execute_query_typed(sql)
