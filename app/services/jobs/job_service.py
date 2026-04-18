"""CRUD and execution management for jobs and their tasks."""

from datetime import UTC, datetime
from time import monotonic
from typing import Any

from sqlalchemy.orm import Session

from app.services.database.models.app import Job, JobExecution, JobTask, TaskExecution
from app.services.database.session import get_session
from app.services.jobs.executors import ExecutorRegistry


class JobService:
    """Provides create/read/update/delete and run operations for DuckBricks jobs."""

    def create_job(self, name: str, description: str | None, schedule_cron: str | None) -> Job:
        with get_session() as session:
            job = Job(name=name, description=description, schedule_cron=schedule_cron)
            session.add(job)
            session.flush()
            session.refresh(job)
            return self._detach(job, session)

    def list_jobs(self) -> list[Job]:
        with get_session() as session:
            jobs = session.query(Job).order_by(Job.created_at.desc()).all()
            for job in jobs:
                _ = job.tasks
                _ = job.executions
            session.expunge_all()
            return jobs

    def get_job(self, job_id: int) -> Job | None:
        with get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                _ = job.tasks
                _ = job.executions
                session.expunge_all()
            return job

    def update_job(self, job_id: int, **fields: Any) -> Job | None:
        with get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None
            for key, value in fields.items():
                setattr(job, key, value)
            session.flush()
            session.refresh(job)
            return self._detach(job, session)

    def delete_job(self, job_id: int) -> bool:
        with get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return False
            session.delete(job)
            return True

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
            return self._detach(task, session)

    def remove_task(self, task_id: int) -> bool:
        with get_session() as session:
            task = session.query(JobTask).filter(JobTask.id == task_id).first()
            if not task:
                return False
            session.delete(task)
            return True

    def run_job(self, job_id: int) -> JobExecution:
        with get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            task_snapshots = [
                {
                    "id": t.id,
                    "executor_type": t.executor_type,
                    "content": t.content,
                    "position": t.position,
                }
                for t in job.tasks
            ]

        execution = self._create_job_execution(job_id)
        self._execute_tasks(execution.id, task_snapshots)
        return self._finalize_job_execution(execution.id)

    def list_executions(self, job_id: int) -> list[JobExecution]:
        with get_session() as session:
            executions = (
                session.query(JobExecution)
                .filter(JobExecution.job_id == job_id)
                .order_by(JobExecution.started_at.desc())
                .limit(50)
                .all()
            )
            for ex in executions:
                _ = ex.task_executions
            session.expunge_all()
            return executions

    def _create_job_execution(self, job_id: int) -> JobExecution:
        with get_session() as session:
            execution = JobExecution(job_id=job_id, status="running")
            session.add(execution)
            session.flush()
            session.refresh(execution)
            return self._detach(execution, session)

    def _execute_tasks(self, execution_id: int, task_snapshots: list[dict[str, Any]]) -> None:
        for snapshot in sorted(task_snapshots, key=lambda t: t["position"]):
            start = monotonic()
            executor = ExecutorRegistry.resolve(snapshot["executor_type"])
            result = executor.execute(snapshot["content"], {})
            duration_ms = int((monotonic() - start) * 1000)
            self._save_task_execution(execution_id, snapshot["id"], result, duration_ms)

    def _save_task_execution(
        self, execution_id: int, task_id: int, result: dict[str, Any], duration_ms: int
    ) -> None:
        with get_session() as session:
            task_exec = TaskExecution(
                job_execution_id=execution_id,
                task_id=task_id,
                status=result["status"],
                completed_at=datetime.now(UTC),
                duration_ms=duration_ms,
                output=result.get("output"),
                error_message=result.get("output") if result["status"] == "error" else None,
            )
            session.add(task_exec)

    def _finalize_job_execution(self, execution_id: int) -> JobExecution:
        with get_session() as session:
            execution = session.query(JobExecution).filter(JobExecution.id == execution_id).first()
            if not execution:
                raise ValueError(f"JobExecution {execution_id} not found")
            task_executions = list(execution.task_executions)
            has_error = any(t.status == "error" for t in task_executions)
            execution.status = "failed" if has_error else "success"
            execution.completed_at = datetime.now(UTC)
            session.flush()
            session.refresh(execution)
            return self._detach(execution, session)

    def _detach(self, instance: Any, session: Session) -> Any:
        session.expunge(instance)
        return instance
