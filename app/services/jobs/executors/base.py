"""Abstract base class for all task executors."""

from abc import ABC, abstractmethod
from typing import Any


class TaskExecutor(ABC):
    """Runs a unit of work (SQL, Python script, etc.) and returns a result dict."""

    @abstractmethod
    def execute(
        self, content: str, context: dict[str, Any], file_path: str | None = None
    ) -> dict[str, Any]:
        """
        Execute the task content and return a result dictionary.

        Args:
            content:   The task body — SQL query, Python script source, etc.
            context:   Runtime context values (e.g., parameters, environment).
            file_path: When provided, executors should prefer running the file
                       directly rather than evaluating the content string.  This
                       is required for file types (e.g., marimo notebooks) that
                       rely on inspect-based source introspection at load time.

        Returns:
            A dict with at minimum: {"status": "success"|"error", "output": str}
        """
