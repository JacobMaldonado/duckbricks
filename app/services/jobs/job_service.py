"""CRUD and execution management for jobs and their tasks."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import UUID

from prefect.client.schemas.objects import FlowRun
from sqlalchemy.orm import Session

from app.config import WORKSPACE_PATH
from app.services.database.models.app import Job, JobTask, JobTaskDependency
from app.services.database.session import get_session
from app.services.jobs.graph_service import JobGraphService, JobGraphValidationError
from app.services.jobs.models import JobDefinitionInput, JobTaskInput, JobTaskSnapshot
from app.services.jobs.schedule_service import JobScheduleService
from app.services.prefect import prefect_client
from app.services.workspace import WorkspaceService

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
                self._load_task_relationships(job)
            session.expunge_all()
            return jobs

    def get_job(self, job_id: int) -> Job | None:
        with get_session() as session:
            job: Job | None = session.query(Job).filter(Job.id == job_id).first()
            if job:
                self._load_task_relationships(job)
                session.expunge_all()
            return job

    def save_job_definition(
        self, definition: JobDefinitionInput, *, job_id: int | None = None
    ) -> Job:
        """Validate and persist a complete job definition as one transaction."""
        normalized_name = definition.name.strip()
        if not normalized_name:
            raise ValueError("Job name is required.")
        if not definition.tasks:
            raise JobGraphValidationError("A job requires at least one task.")

        JobScheduleService.validate(definition.schedule_cron, definition.schedule_timezone)
        normalized_tasks = self._normalize_task_sources(definition.tasks)
        JobGraphService.validate_inputs(normalized_tasks)

        with get_session() as session:
            if job_id is None:
                persisted_job = Job()
                job = persisted_job
                session.add(job)
            else:
                existing_job = session.query(Job).filter(Job.id == job_id).first()
                if not existing_job:
                    raise ValueError(f"Job {job_id} not found.")
                job = existing_job

            job.name = normalized_name
            job.description = definition.description.strip() if definition.description else None
            job.schedule_cron = definition.schedule_cron
            job.schedule_timezone = definition.schedule_timezone
            job.is_enabled = definition.is_enabled
            job.graph_version = 1
            session.flush()

            existing_tasks = {task.id: task for task in job.tasks}
            retained_ids: set[int] = set()
            task_by_key: dict[str, JobTask] = {}
            for position, task_input in enumerate(normalized_tasks):
                task = existing_tasks.get(task_input.task_id) if task_input.task_id else None
                if task_input.task_id and not task:
                    raise ValueError(f"Task {task_input.task_id} does not belong to job {job.id}.")
                if task is None:
                    task = JobTask(job_id=job.id)
                    session.add(task)
                task.name = task_input.name.strip()
                task.executor_type = task_input.executor_type
                task.content = task_input.legacy_content if not task_input.file_path else ""
                task.file_path = task_input.file_path
                task.position = position
                session.flush()
                retained_ids.add(task.id)
                task_by_key[task_input.key] = task

            all_existing_ids = set(existing_tasks)
            all_persisted_ids = retained_ids | all_existing_ids
            if all_persisted_ids:
                session.query(JobTaskDependency).filter(
                    JobTaskDependency.task_id.in_(all_persisted_ids)
                ).delete(synchronize_session=False)

            for removed_id in all_existing_ids - retained_ids:
                session.delete(existing_tasks[removed_id])
            session.flush()

            input_by_key = {task.key: task for task in normalized_tasks}
            for key, task in task_by_key.items():
                for dependency_key in input_by_key[key].depends_on:
                    session.add(
                        JobTaskDependency(
                            task_id=task.id,
                            depends_on_task_id=task_by_key[dependency_key].id,
                        )
                    )
            session.flush()
            saved_job_id = job.id

        saved_job = self.get_job(saved_job_id)
        if not saved_job:
            raise RuntimeError(f"Job {saved_job_id} disappeared after it was saved.")
        if job_id is None:
            self._register_deployment(saved_job)
        else:
            self._sync_deployment(saved_job)
        return saved_job

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

    def get_task_snapshots(self, job_id: int) -> list[JobTaskSnapshot]:
        """Return ordered task snapshots for a job, ready for Prefect task execution."""
        with get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            return [
                JobTaskSnapshot(
                    task_id=task.id,
                    name=task.name,
                    executor_type=task.executor_type,
                    legacy_content=task.content,
                    file_path=task.file_path,
                    position=task.position,
                    dependency_ids=tuple(edge.depends_on_task_id for edge in task.dependency_edges),
                )
                for task in sorted(job.tasks, key=lambda item: item.position)
            ]

    @staticmethod
    def _load_task_relationships(job: Job) -> None:
        for task in job.tasks:
            _ = task.dependency_edges

    @staticmethod
    def _normalize_task_sources(
        tasks: tuple[JobTaskInput, ...],
    ) -> tuple[JobTaskInput, ...]:
        workspace = WorkspaceService(WORKSPACE_PATH)
        normalized: list[JobTaskInput] = []
        for task in tasks:
            if not task.file_path:
                normalized.append(task)
                continue
            source_path = Path(task.file_path)
            try:
                relative_path = (
                    workspace.relative_path(str(source_path))
                    if source_path.is_absolute()
                    else str(source_path)
                )
                absolute_path = Path(workspace.absolute_path(relative_path))
            except (ValueError, OSError) as exc:
                raise JobGraphValidationError(
                    f"Task '{task.name}' points outside the workspace."
                ) from exc
            if not absolute_path.is_file():
                raise JobGraphValidationError(
                    f"Workspace file for task '{task.name}' does not exist: {relative_path}."
                )
            executor_type = JobGraphService.executor_for_path(relative_path)
            normalized.append(
                JobTaskInput(
                    key=task.key,
                    name=task.name,
                    file_path=relative_path,
                    executor_type=executor_type,
                    depends_on=task.depends_on,
                    task_id=task.task_id,
                    legacy_content=task.legacy_content,
                )
            )
        return tuple(normalized)

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

    def _detach(self, instance: Any, session: Session) -> Any:
        session.expunge(instance)
        return instance
