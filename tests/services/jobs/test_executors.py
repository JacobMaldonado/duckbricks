"""Tests for the task executor pattern."""

import pytest

from app.services.jobs.executors.base import TaskExecutor
from app.services.jobs.executors.python_executor import PythonTaskExecutor
from app.services.jobs.executors.registry import ExecutorRegistry


class TestPythonTaskExecutor:
    def test_executes_valid_python_script(self):
        executor = PythonTaskExecutor()
        result = executor.execute("x = 1 + 1\nprint(x)", {})
        assert result["status"] == "success"
        assert "2" in result["output"]

    def test_returns_error_on_syntax_error(self):
        executor = PythonTaskExecutor()
        result = executor.execute("this is not valid python!!!", {})
        assert result["status"] == "error"
        assert result["output"]

    def test_captures_print_output(self):
        executor = PythonTaskExecutor()
        result = executor.execute('print("hello duckbricks")', {})
        assert result["status"] == "success"
        assert "hello duckbricks" in result["output"]


class TestExecutorRegistry:
    def test_registered_types_include_sql_and_python(self):
        types = ExecutorRegistry.available_types()
        assert "sql" in types
        assert "python" in types

    def test_resolves_python_executor(self):
        executor = ExecutorRegistry.resolve("python")
        assert isinstance(executor, TaskExecutor)

    def test_raises_for_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown executor type"):
            ExecutorRegistry.resolve("nonexistent_executor_xyz")
