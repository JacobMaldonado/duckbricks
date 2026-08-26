"""Prefect flow definitions for DuckBricks job execution."""

import logging
from pathlib import Path
from typing import Any

from prefect import flow, task
from prefect.futures import PrefectFuture

from app.config import WORKSPACE_PATH
from app.services.jobs.graph_service import JobGraphService
from app.services.jobs.models import JobTaskSnapshot
from app.services.workspace import WorkspaceService

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


def _resolve_source(snapshot: JobTaskSnapshot) -> tuple[str, str | None]:
    """Return task content and a safe absolute path for file-based execution."""
    if not snapshot.file_path:
        return snapshot.legacy_content, None
    workspace = WorkspaceService(WORKSPACE_PATH)
    source_path = Path(snapshot.file_path)
    relative_path = (
        workspace.relative_path(str(source_path)) if source_path.is_absolute() else str(source_path)
    )
    content = workspace.read_file(relative_path)
    return content, workspace.absolute_path(relative_path)


@task(log_prints=True)
def execute_task(snapshot: JobTaskSnapshot) -> dict[str, Any]:
    """Execute a single DuckBricks task as a tracked Prefect task.

    Resolves the task content (inline or file), dispatches to the correct
    executor, and raises on failure so Prefect marks the task as Failed.
    """
    from app.services.jobs.executors import ExecutorRegistry

    content, absolute_path = _resolve_source(snapshot)
    executor = ExecutorRegistry.resolve(snapshot.executor_type)
    result = executor.execute(content, {}, file_path=absolute_path)
    if result.get("status") == "error":
        raise RuntimeError(result.get("output", "unknown error"))
    return result


@flow(name="duckbricks-job", log_prints=True)
def run_job_flow(job_id: int) -> None:
    """Execute a DuckBricks job as a tracked Prefect flow run.

    Each job task becomes an individual Prefect task so the Prefect UI shows
    per-task state, logs, and duration. Explicit dependency edges are passed
    through ``wait_for`` so independent branches may run concurrently.
    """
    from app.services.jobs.job_service import JobService

    _bootstrap_worker_services()
    futures_by_task_id = _submit_task_graph(JobService().get_task_snapshots(job_id), job_id)
    _resolve_task_graph(futures_by_task_id)


def _submit_task_graph(
    snapshots: list[JobTaskSnapshot], job_id: int
) -> dict[int, PrefectFuture[dict[str, Any]]]:
    """Submit a validated task graph and return each task's Prefect future."""
    ordered_snapshots = JobGraphService.order_snapshots(snapshots)
    futures_by_task_id: dict[int, PrefectFuture[dict[str, Any]]] = {}
    for snapshot in ordered_snapshots:
        task_name = snapshot.name or f"task-{snapshot.position + 1}"
        upstream_futures = [
            futures_by_task_id[dependency_id] for dependency_id in snapshot.dependency_ids
        ]
        futures_by_task_id[snapshot.task_id] = execute_task.with_options(
            name=task_name,
            task_run_name=task_name,
            tags=[f"job-id:{job_id}", f"job-task-id:{snapshot.task_id}"],
        ).submit(snapshot, wait_for=upstream_futures, return_state=False)
    return futures_by_task_id


def _resolve_task_graph(futures_by_task_id: dict[int, PrefectFuture[dict[str, Any]]]) -> None:
    """Wait for every submitted branch and propagate any terminal failure."""
    for future in futures_by_task_id.values():
        future.wait()
    for future in futures_by_task_id.values():
        future.result()
