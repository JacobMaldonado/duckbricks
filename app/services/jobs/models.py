"""Typed job-definition values shared by persistence, execution, and UI layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class JobTaskInput:
    """A task submitted by the job editor."""

    key: str
    name: str
    file_path: str | None
    executor_type: str
    depends_on: tuple[str, ...] = ()
    task_id: int | None = None
    legacy_content: str = ""


@dataclass(frozen=True, slots=True)
class JobDefinitionInput:
    """A complete job definition saved as one transaction."""

    name: str
    description: str | None
    schedule_cron: str | None
    schedule_timezone: str = "UTC"
    is_enabled: bool = True
    tasks: tuple[JobTaskInput, ...] = ()


@dataclass(frozen=True, slots=True)
class JobTaskSnapshot:
    """Persisted task data required by the Prefect flow runner."""

    task_id: int
    name: str
    executor_type: str
    file_path: str | None
    legacy_content: str
    position: int
    dependency_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class JobRunSummary:
    """Framework-neutral representation of a Prefect flow run."""

    run_id: UUID
    deployment_id: UUID | None
    name: str
    state: str
    started_at: datetime | None
    ended_at: datetime | None
    expected_start_time: datetime | None
    duration_seconds: float | None
    run_count: int


@dataclass(frozen=True, slots=True)
class TaskRunSummary:
    """Framework-neutral representation of a Prefect task run."""

    task_run_id: UUID
    name: str
    state: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: float | None
    run_count: int
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RunLogEntry:
    """A single Prefect flow/task log line."""

    timestamp: datetime
    level: int
    message: str
    task_run_id: UUID | None


@dataclass(slots=True)
class JobTelemetry:
    """Recent orchestration information grouped by deployment."""

    latest_run: JobRunSummary | None = None
    next_run: JobRunSummary | None = None
    recent_runs: list[JobRunSummary] = field(default_factory=list)
