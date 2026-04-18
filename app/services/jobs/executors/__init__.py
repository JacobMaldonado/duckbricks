"""Task executor implementations and registry."""

from app.services.jobs.executors.python_executor import PythonTaskExecutor
from app.services.jobs.executors.registry import ExecutorRegistry
from app.services.jobs.executors.sql_executor import SqlTaskExecutor

ExecutorRegistry.register("sql", SqlTaskExecutor)
ExecutorRegistry.register("python", PythonTaskExecutor)

__all__ = ["ExecutorRegistry", "SqlTaskExecutor", "PythonTaskExecutor"]
