"""Prefect-based scheduler that builds and runs flows from job definitions."""

import threading
from typing import Any

from prefect import flow, task
from prefect.client.schemas.schedules import CronSchedule

from app.services.jobs.executors import ExecutorRegistry


class JobScheduler:
    """Manages in-process Prefect flows and schedules for DuckBricks jobs."""

    _running_deployments: dict[int, Any] = {}
    _lock = threading.Lock()

    @classmethod
    def build_flow(cls, job_id: int, job_name: str, tasks_config: list[dict[str, Any]]):
        """Build a Prefect flow function from a job's task list."""

        @flow(name=f"job-{job_id}-{job_name}")
        def job_flow():
            for task_config in sorted(tasks_config, key=lambda t: t["position"]):
                cls._run_task(task_config["executor_type"], task_config["content"])

        return job_flow

    @staticmethod
    @task
    def _run_task(executor_type: str, content: str) -> dict[str, Any]:
        executor = ExecutorRegistry.resolve(executor_type)
        return executor.execute(content, {})

    @classmethod
    def schedule_job(
        cls,
        job_id: int,
        job_name: str,
        cron_expression: str,
        tasks_config: list[dict[str, Any]],
    ) -> None:
        """Register a Prefect flow with a cron schedule in a background thread."""
        with cls._lock:
            job_flow = cls.build_flow(job_id, job_name, tasks_config)
            schedule = CronSchedule(cron=cron_expression)

            def serve_flow():
                job_flow.serve(name=f"job-{job_id}", schedules=[schedule])

            thread = threading.Thread(
                target=serve_flow, daemon=True, name=f"job-scheduler-{job_id}"
            )
            thread.start()
            cls._running_deployments[job_id] = thread

    @classmethod
    def unschedule_job(cls, job_id: int) -> None:
        """Remove a scheduled job (marks thread for removal; daemon threads stop with app)."""
        with cls._lock:
            cls._running_deployments.pop(job_id, None)

    @classmethod
    def run_now(
        cls, job_id: int, job_name: str, tasks_config: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Execute a job immediately as a Prefect flow run (blocking)."""
        job_flow = cls.build_flow(job_id, job_name, tasks_config)
        return job_flow()
