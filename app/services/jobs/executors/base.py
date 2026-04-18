"""Abstract base class for all task executors."""

from abc import ABC, abstractmethod
from typing import Any


class TaskExecutor(ABC):
    """Runs a unit of work (SQL, Python script, etc.) and returns a result dict."""

    @abstractmethod
    def execute(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the task content and return a result dictionary.

        Args:
            content: The task body — SQL query, Python script, file path, etc.
            context: Runtime context values (e.g., parameters, environment variables).

        Returns:
            A dict with at minimum: {"status": "success"|"error", "output": str}
        """
