"""Prefect flow definitions for DuckBricks job execution."""

from prefect import flow

from app.services.jobs.job_service import JobService


@flow(name="duckbricks-job", log_prints=True)
def run_job_flow(job_id: int) -> None:
    """Execute a DuckBricks job as a tracked Prefect flow run."""
    JobService().run_job(job_id)
