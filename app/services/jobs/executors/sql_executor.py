"""Executes SQL statements via the DuckBricks QueryEngine."""

from typing import Any

from app.services.jobs.executors.base import TaskExecutor
from app.services.metastore import manager


class SqlTaskExecutor(TaskExecutor):
    """Runs a SQL query against the DuckLake catalog and returns row count + preview."""

    def execute(
        self, content: str, context: dict[str, Any], file_path: str | None = None
    ) -> dict[str, Any]:
        result = manager.execute_query(content)
        if not result.get("success", False):
            return {"status": "error", "output": result.get("error", "Unknown error")}
        row_count = len(result.get("rows", []))
        return {
            "status": "success",
            "output": f"Query completed. {row_count} rows affected/returned.",
        }
