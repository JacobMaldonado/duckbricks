"""Executes Python scripts in a sandboxed namespace or as a subprocess."""

import io
import os
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
        """Run a Python file as a subprocess, streaming each output line in real-time.

        PYTHONUNBUFFERED=1 ensures the child process flushes stdout immediately
        instead of batching into the OS pipe buffer. Each line is printed so
        Prefect's log_prints=True captures it as a structured log record.
        """
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        process = subprocess.Popen(  # noqa: S603
            [sys.executable, file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        output_lines: list[str] = []
        for raw_line in process.stdout:  # type: ignore[union-attr]
            line = raw_line.rstrip("\n")
            print(line, flush=True)
            output_lines.append(line)
        process.wait()
        if process.returncode != 0:
            return {"status": "error", "output": "\n".join(output_lines)}
        return {"status": "success", "output": "\n".join(output_lines)}

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
