"""Prefect flow definitions for DuckBricks job execution."""

import logging
from typing import Any

from prefect import flow, task
from prefect.futures import PrefectFuture

_log = logging.getLogger(__name__)


def _bootstrap_worker_services() -> None:
    """Initialize the database and metastore for execution inside a Prefect worker.

    The worker process is started independently of the main app, so it does not
    go through the NiceGUI startup lifecycle. This function replicates the
    essential initialization steps so task executors have everything they need.
    """
    from app.services.database.session import init_database
    from app.services.metastore import manager

    try:
        init_database()
        _log.info("Worker: database initialized.")
    except Exception as exc:
        _log.warning("Worker: database initialization failed: %s", exc)
    try:
        manager.initialize()
        _log.info("Worker: metastore initialized.")
    except Exception as exc:
        _log.warning("Worker: metastore initialization failed: %s", exc)


def _resolve_content(snapshot: dict[str, Any]) -> str:
    """Return inline content or read from file_path if one is set."""
    file_path: str | None = snapshot.get("file_path")
    if not file_path:
        content: str = snapshot.get("content", "") or ""
        return content
    with open(file_path) as fh:
        return fh.read()


@task(log_prints=True)
def execute_task(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Execute a single DuckBricks task as a tracked Prefect task.

    Resolves the task content (inline or file), dispatches to the correct
    executor, and raises on failure so Prefect marks the task as Failed.
    """
    from app.services.jobs.executors import ExecutorRegistry

    content = _resolve_content(snapshot)
    file_path: str | None = snapshot.get("file_path")
    executor = ExecutorRegistry.resolve(snapshot["executor_type"])
    result = executor.execute(content, {}, file_path=file_path)
    if result.get("status") == "error":
        raise RuntimeError(result.get("output", "unknown error"))
    return result


@flow(name="duckbricks-job", log_prints=True)
def run_job_flow(job_id: int) -> None:
    """Execute a DuckBricks job as a tracked Prefect flow run.

    Each job task becomes an individual Prefect task so the Prefect UI shows
    per-task state, logs, and duration. Tasks are chained with wait_for so
    that each task depends on the previous one, reflecting the position-based
    execution order.
    """
    from app.services.jobs.job_service import JobService

    _bootstrap_worker_services()
    snapshots = JobService().get_task_snapshots(job_id)

    previous_future: PrefectFuture[dict[str, Any]] | None = None
    for snapshot in snapshots:
        task_name = snapshot.get("name") or f"task-{snapshot['position'] + 1}"
        wait_for = [previous_future] if previous_future is not None else []
        previous_future = execute_task.with_options(name=task_name).submit(
            snapshot, wait_for=wait_for
        )

    if previous_future is not None:
        previous_future.result()
