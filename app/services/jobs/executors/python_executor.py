"""Executes Python scripts in a sandboxed namespace or as a subprocess."""

import io
import subprocess
import sys
import traceback
from contextlib import redirect_stdout
from typing import Any

from app.services.jobs.executors.base import TaskExecutor


class PythonTaskExecutor(TaskExecutor):
    """Runs a Python script using exec() for inline content or subprocess for file paths.

    File-based execution is required when the script relies on inspect-based
    source introspection at import time (e.g., marimo notebooks), because exec()
    compiles code with __code__.co_filename = '<string>' which breaks inspect.
    Running the file as a real subprocess preserves the correct file path.
    """

    def execute(
        self, content: str, context: dict[str, Any], file_path: str | None = None
    ) -> dict[str, Any]:
        if file_path:
            return self._execute_file(file_path)
        return self._execute_inline(content, context)

    def _execute_file(self, file_path: str) -> dict[str, Any]:
        """Run a Python file as a subprocess so inspect and __file__ work correctly."""
        result = subprocess.run(  # noqa: S603
            [sys.executable, file_path],
            capture_output=True,
            text=True,
        )
        output = result.stdout
        if result.returncode != 0:
            error_detail = result.stderr or result.stdout or "Process exited with non-zero status"
            return {"status": "error", "output": error_detail}
        return {"status": "success", "output": output}

    def _execute_inline(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """Run an inline Python script string using exec() in an isolated namespace."""
        namespace: dict[str, Any] = {"__builtins__": __builtins__, "context": context}
        output_buffer = io.StringIO()
        try:
            with redirect_stdout(output_buffer):
                exec(content, namespace)  # noqa: S102
            return {"status": "success", "output": output_buffer.getvalue()}
        except Exception:
            return {"status": "error", "output": traceback.format_exc()}
