"""Executes Python scripts in a sandboxed namespace or as a subprocess."""

import io
import os
import shutil
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

    When a file contains PEP 723 inline script metadata (``# /// script``),
    it is executed via ``uv run --isolated`` so that its declared dependencies
    are installed in an isolated virtual environment automatically.
    """

    _SANDBOX_MARKER = "# /// script"
    _SANDBOX_READ_BYTES = 4096

    def execute(
        self, content: str, context: dict[str, Any], file_path: str | None = None
    ) -> dict[str, Any]:
        if file_path:
            return self._execute_file(file_path)
        return self._execute_inline(content, context)

    def _is_sandboxed_script(self, file_path: str) -> bool:
        """Return True if the file declares PEP 723 inline script metadata."""
        try:
            with open(file_path) as fh:
                header = fh.read(self._SANDBOX_READ_BYTES)
            return self._SANDBOX_MARKER in header
        except OSError:
            return False

    def _build_command(self, file_path: str) -> list[str]:
        """Return the subprocess command appropriate for this file.

        Sandboxed scripts require ``uv``. If ``uv`` is not on PATH the error
        is surfaced immediately with an actionable message.
        """
        if self._is_sandboxed_script(file_path):
            uv = shutil.which("uv")
            if uv is None:
                raise RuntimeError(
                    "This script requires 'uv' for sandboxed execution but 'uv' was not "
                    "found on PATH. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
                )
            return [uv, "run", "--isolated", file_path]
        return [sys.executable, file_path]

    def _execute_file(self, file_path: str) -> dict[str, Any]:
        """Run a Python file as a subprocess, streaming each output line in real-time.

        Sandboxed files (PEP 723 inline metadata) are executed via
        ``uv run --isolated`` so their declared dependencies are resolved
        automatically. All other files use the current Python interpreter.

        PYTHONUNBUFFERED=1 ensures the child process flushes stdout immediately
        instead of batching into the OS pipe buffer. Each line is printed so
        Prefect's log_prints=True captures it as a structured log record.
        """
        from app.config import HELPERS_PATH

        python_path = os.pathsep.join(
            filter(None, [HELPERS_PATH, os.environ.get("PYTHONPATH", "")])
        )
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONPATH": python_path}
        process = subprocess.Popen(  # noqa: S603
            self._build_command(file_path),
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
