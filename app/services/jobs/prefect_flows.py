"""Prefect flow definitions for DuckBricks job execution."""

import logging

from prefect import flow

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


@flow(name="duckbricks-job", log_prints=True)
def run_job_flow(job_id: int) -> None:
    """Execute a DuckBricks job as a tracked Prefect flow run.

    This flow is the entry point for Prefect workers. It bootstraps the
    required services and then runs all job tasks sequentially.
    """
    from app.services.jobs.job_service import JobService

    _bootstrap_worker_services()
    JobService().execute_job_tasks(job_id)
