"""CRUD and execution management for jobs and their tasks."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from typing import Any
from uuid import UUID

from prefect.client.schemas.objects import FlowRun
from sqlalchemy.orm import Session

from app.services.database.models.app import Job, JobTask
from app.services.database.session import get_session
from app.services.jobs.executors import ExecutorRegistry
from app.services.prefect import prefect_client

_log = logging.getLogger(__name__)

_prefect_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="prefect-sync")


def _run_prefect(coro: Any) -> Any:
    """Execute a Prefect API coroutine from a synchronous context.

    Submits the coroutine to a dedicated thread pool so that it runs in its own
    event loop, safely isolated from NiceGUI's main async event loop.
    """
    future = _prefect_executor.submit(asyncio.run, coro)
    return future.result()


class JobService:
    """Provides create/read/update/delete and run operations for DuckBricks jobs."""

    def create_job(self, name: str, description: str | None, schedule_cron: str | None) -> Job:
        with get_session() as session:
            job = Job(name=name, description=description, schedule_cron=schedule_cron)
            session.add(job)
            session.flush()
            session.refresh(job)
            detached: Job = self._detach(job, session)
        self._register_deployment(detached)
        return detached

    def list_jobs(self) -> list[Job]:
        with get_session() as session:
            jobs: list[Job] = session.query(Job).order_by(Job.created_at.desc()).all()
            for job in jobs:
                _ = job.tasks
            session.expunge_all()
            return jobs

    def get_job(self, job_id: int) -> Job | None:
        with get_session() as session:
            job: Job | None = session.query(Job).filter(Job.id == job_id).first()
            if job:
                _ = job.tasks
                session.expunge_all()
            return job

    def update_job(self, job_id: int, **fields: Any) -> Job | None:
        with get_session() as session:
            job: Job | None = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None
            for key, value in fields.items():
                setattr(job, key, value)
            session.flush()
            session.refresh(job)
            detached: Job = self._detach(job, session)
        self._sync_deployment(detached)
        return detached

    def delete_job(self, job_id: int) -> bool:
        with get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return False
            deployment_id = job.prefect_deployment_id
            session.delete(job)
        if deployment_id:
            try:
                _run_prefect(prefect_client.delete_deployment(UUID(deployment_id)))
            except Exception as exc:
                _log.warning("Could not delete Prefect deployment %s: %s", deployment_id, exc)
        return True

    def toggle_enabled(self, job_id: int) -> Job | None:
        """Toggle the is_enabled flag on a job and pause or resume its Prefect deployment."""
        with get_session() as session:
            job: Job | None = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None
            job.is_enabled = not job.is_enabled
            session.flush()
            session.refresh(job)
            detached: Job = self._detach(job, session)
        self._sync_deployment(detached)
        return detached

    def add_task(
        self, job_id: int, name: str, executor_type: str, content: str, position: int = 0
    ) -> JobTask:
        with get_session() as session:
            task = JobTask(
                job_id=job_id,
                name=name,
                executor_type=executor_type,
                content=content,
                position=position,
            )
            session.add(task)
            session.flush()
            session.refresh(task)
            result: JobTask = self._detach(task, session)
            return result

    def replace_tasks(self, job_id: int, task_dicts: list[dict]) -> None:
        """Delete all existing tasks for a job and insert the provided list."""
        with get_session() as session:
            session.query(JobTask).filter(JobTask.job_id == job_id).delete()
            for idx, td in enumerate(task_dicts):
                task = JobTask(
                    job_id=job_id,
                    name=td.get("name") or f"Task {idx + 1}",
                    executor_type=td.get("executor_type", "sql"),
                    content=td.get("content", ""),
                    file_path=td.get("file_path"),
                    position=idx,
                )
                session.add(task)

    def remove_task(self, task_id: int) -> bool:
        with get_session() as session:
            task = session.query(JobTask).filter(JobTask.id == task_id).first()
            if not task:
                return False
            session.delete(task)
            return True

    def run_job(self, job_id: int) -> FlowRun:
        """Trigger an immediate Prefect flow run for the job and return the FlowRun."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if not job.prefect_deployment_id:
            raise ValueError(
                f"Job {job_id} has no Prefect deployment. Save the job again to register it."
            )
        result: FlowRun = _run_prefect(prefect_client.trigger_run(UUID(job.prefect_deployment_id)))
        return result

    def list_executions(self, job_id: int, limit: int = 50) -> list[FlowRun]:
        """Return recent Prefect flow runs for the job, newest first."""
        job = self.get_job(job_id)
        if not job or not job.prefect_deployment_id:
            return []
        try:
            runs: list[FlowRun] = _run_prefect(
                prefect_client.list_runs(UUID(job.prefect_deployment_id), limit=limit)
            )
            return runs
        except Exception as exc:
            _log.warning("Could not fetch run history for job %d: %s", job_id, exc)
            return []

    def execute_job_tasks(self, job_id: int) -> None:
        """Run all tasks for a job sequentially.

        This method is called by the Prefect worker via run_job_flow(). It
        performs direct task execution without interacting with Prefect, so
        the worker avoids triggering a recursive deployment loop.
        """
        with get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            task_snapshots = [
                {
                    "id": t.id,
                    "executor_type": t.executor_type,
                    "content": t.content,
                    "file_path": t.file_path,
                    "position": t.position,
                }
                for t in job.tasks
            ]
        self._execute_tasks(task_snapshots)

    def _register_deployment(self, job: Job) -> None:
        try:
            deployment_id = _run_prefect(prefect_client.create_deployment(job))
            with get_session() as session:
                db_job = session.query(Job).filter(Job.id == job.id).first()
                if db_job:
                    db_job.prefect_deployment_id = str(deployment_id)
            job.prefect_deployment_id = str(deployment_id)
        except Exception as exc:
            _log.warning("Could not create Prefect deployment for job %d: %s", job.id, exc)

    def _sync_deployment(self, job: Job) -> None:
        if not job.prefect_deployment_id:
            self._register_deployment(job)
            return
        deployment_id = UUID(job.prefect_deployment_id)
        try:
            _run_prefect(prefect_client.update_deployment(deployment_id, job))
        except Exception as exc:
            _log.warning("Could not update Prefect deployment %s: %s", deployment_id, exc)

    def _execute_tasks(self, task_snapshots: list[dict[str, Any]]) -> None:
        for snapshot in sorted(task_snapshots, key=lambda t: t["position"]):
            content = self._resolve_task_content(snapshot)
            start = monotonic()
            executor = ExecutorRegistry.resolve(snapshot["executor_type"])
            result = executor.execute(content, {})
            duration_ms = int((monotonic() - start) * 1000)
            status = "failed" if result["status"] == "error" else result["status"]
            _log.info(
                "Task %d finished in %dms with status=%s", snapshot["id"], duration_ms, status
            )

    def _resolve_task_content(self, snapshot: dict[str, Any]) -> str:
        """Return inline content or read from file_path if one is set."""
        file_path: str | None = snapshot.get("file_path")
        if not file_path:
            content: str = snapshot.get("content", "")
            return content
        try:
            with open(file_path) as fh:
                return fh.read()
        except OSError as exc:
            raise ValueError(f"Cannot read task file '{file_path}': {exc}") from exc

    def _detach(self, instance: Any, session: Session) -> Any:
        session.expunge(instance)
        return instance
