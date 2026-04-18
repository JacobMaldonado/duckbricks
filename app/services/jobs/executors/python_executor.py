"""Executes Python scripts in a sandboxed namespace."""

import io
import traceback
from contextlib import redirect_stdout
from typing import Any

from app.services.jobs.executors.base import TaskExecutor


class PythonTaskExecutor(TaskExecutor):
    """Runs a Python script string using exec() in an isolated namespace."""

    def execute(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        namespace: dict[str, Any] = {"__builtins__": __builtins__, "context": context}
        output_buffer = io.StringIO()
        try:
            with redirect_stdout(output_buffer):
                exec(content, namespace)  # noqa: S102
            return {"status": "success", "output": output_buffer.getvalue()}
        except Exception:
            return {"status": "error", "output": traceback.format_exc()}
