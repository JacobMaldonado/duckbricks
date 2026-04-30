"""Prefect flow definitions for DuckBricks job execution."""

from prefect import flow

from app.services.jobs.job_service import JobService


@flow(name="duckbricks-job", log_prints=True)
def run_job_flow(job_id: int) -> None:
    """Execute a DuckBricks job as a tracked Prefect flow run.

    This flow is the entry point for Prefect workers. It calls
    execute_job_tasks() directly so task execution stays within the worker
    process without triggering another Prefect deployment round-trip.
    """
    JobService().execute_job_tasks(job_id)
