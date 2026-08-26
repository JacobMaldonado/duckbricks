"""Prefect-backed orchestration telemetry for the DuckBricks Jobs UI."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from uuid import UUID

from prefect.client.schemas.objects import FlowRun, Log, TaskRun

from app.services.database.models.app import Job
from app.services.jobs.models import (
    JobRunSummary,
    JobTelemetry,
    RunLogEntry,
    TaskRunSummary,
)
from app.services.prefect.client import PrefectApiClient


class JobTelemetryService:
    """Aggregates Prefect models into stable, UI-focused values."""

    def __init__(self, prefect_api: PrefectApiClient) -> None:
        self._prefect_api = prefect_api

    async def load_dashboard(self, jobs: Sequence[Job]) -> dict[int, JobTelemetry]:
        deployment_to_job: dict[UUID, int] = {
            UUID(job.prefect_deployment_id): job.id for job in jobs if job.prefect_deployment_id
        }
        result = {job.id: JobTelemetry() for job in jobs}
        if not deployment_to_job:
            return result

        deployment_ids = list(deployment_to_job)
        recent_runs, scheduled_runs = await asyncio.gather(
            self._prefect_api.list_runs_for_deployments(deployment_ids),
            self._prefect_api.list_scheduled_runs(deployment_ids),
        )

        for run in recent_runs:
            if not run.deployment_id or run.deployment_id not in deployment_to_job:
                continue
            telemetry = result[deployment_to_job[run.deployment_id]]
            summary = self._flow_run_summary(run)
            telemetry.recent_runs.append(summary)
            if telemetry.latest_run is None:
                telemetry.latest_run = summary

        for run in scheduled_runs:
            if not run.deployment_id or run.deployment_id not in deployment_to_job:
                continue
            telemetry = result[deployment_to_job[run.deployment_id]]
            if telemetry.next_run is None:
                telemetry.next_run = self._flow_run_summary(run)
        return result

    async def load_job_runs(self, job: Job, limit: int = 50) -> list[JobRunSummary]:
        if not job.prefect_deployment_id:
            return []
        runs = await self._prefect_api.list_runs(
            UUID(job.prefect_deployment_id),
            limit=limit,
        )
        return [self._flow_run_summary(run) for run in runs]

    async def load_run(self, flow_run_id: UUID) -> JobRunSummary:
        """Return one flow run by ID."""
        return self._flow_run_summary(await self._prefect_api.get_run(flow_run_id))

    async def load_task_runs(self, flow_run_id: UUID) -> list[TaskRunSummary]:
        runs = await self._prefect_api.list_task_runs(flow_run_id)
        return [self._task_run_summary(run) for run in runs]

    async def load_logs(
        self,
        flow_run_id: UUID,
        *,
        task_run_id: UUID | None = None,
        limit: int = 500,
    ) -> list[RunLogEntry]:
        logs = await self._prefect_api.list_logs(
            flow_run_id,
            task_run_id=task_run_id,
            limit=limit,
        )
        return [self._log_entry(log) for log in logs]

    @staticmethod
    def _flow_run_summary(run: FlowRun) -> JobRunSummary:
        duration = run.total_run_time.total_seconds() if run.total_run_time is not None else None
        return JobRunSummary(
            run_id=run.id,
            deployment_id=run.deployment_id,
            name=run.name or str(run.id),
            state=(run.state_name or "UNKNOWN").upper(),
            started_at=run.start_time,
            ended_at=run.end_time,
            expected_start_time=run.expected_start_time,
            duration_seconds=duration,
            run_count=run.run_count,
        )

    @staticmethod
    def _task_run_summary(run: TaskRun) -> TaskRunSummary:
        duration = run.total_run_time.total_seconds() if run.total_run_time is not None else None
        return TaskRunSummary(
            task_run_id=run.id,
            name=run.name,
            state=(run.state_name or "UNKNOWN").upper(),
            started_at=run.start_time,
            ended_at=run.end_time,
            duration_seconds=duration,
            run_count=run.run_count,
            tags=tuple(run.tags or ()),
        )

    @staticmethod
    def _log_entry(log: Log) -> RunLogEntry:
        return RunLogEntry(
            timestamp=log.timestamp,
            level=log.level,
            message=log.message,
            task_run_id=log.task_run_id,
        )
