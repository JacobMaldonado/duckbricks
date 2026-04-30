"""Cron-driven scheduler that executes DuckBricks jobs as Prefect flow runs."""

import asyncio
import logging
from datetime import UTC, datetime

from croniter import croniter  # type: ignore[import-untyped]

from app.services.jobs.prefect_flows import run_job_flow

_log = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 30


class PrefectJobScheduler:
    """Schedules enabled DuckBricks jobs and runs them as Prefect flow runs.

    Each scheduled job is checked every poll interval against its cron expression.
    When due, the corresponding Prefect flow is triggered in a thread-pool executor
    so it does not block the NiceGUI asyncio event loop.
    """

    def __init__(self) -> None:
        self._schedule: dict[int, str] = {}
        self._last_triggered: dict[int, datetime] = {}
        self._loop_task: asyncio.Task | None = None

    def start(self) -> None:
        """Spawn the background cron-polling asyncio task."""
        if self._loop_task and not self._loop_task.done():
            return
        self._loop_task = asyncio.ensure_future(self._run_scheduler_loop())
        _log.info("PrefectJobScheduler started.")

    def shutdown(self) -> None:
        """Cancel the background cron-polling task."""
        if self._loop_task:
            self._loop_task.cancel()
            self._loop_task = None
        _log.info("PrefectJobScheduler stopped.")

    def sync_from_database(self) -> None:
        """Load all enabled jobs that have a cron expression from the database."""
        from app.services.jobs.job_service import JobService

        jobs = JobService().list_jobs()
        self._schedule.clear()
        for job in jobs:
            if job.is_enabled and job.schedule_cron:
                self._schedule[job.id] = job.schedule_cron
        _log.info("Synced %d scheduled job(s) from database.", len(self._schedule))

    def schedule_job(self, job_id: int, cron_expression: str) -> None:
        """Register or update a job in the in-memory cron schedule."""
        self._schedule[job_id] = cron_expression
        _log.debug("Scheduled job %d with cron '%s'.", job_id, cron_expression)

    def unschedule_job(self, job_id: int) -> None:
        """Remove a job from the in-memory cron schedule."""
        self._schedule.pop(job_id, None)
        self._last_triggered.pop(job_id, None)
        _log.debug("Unscheduled job %d.", job_id)

    def reschedule_job(self, job_id: int, cron_expression: str) -> None:
        """Update the cron expression for an already-scheduled job."""
        self._last_triggered.pop(job_id, None)
        self.schedule_job(job_id, cron_expression)

    async def _run_scheduler_loop(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                _log.exception("Unexpected error in scheduler loop.")
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    async def _tick(self) -> None:
        now = datetime.now(UTC)
        for job_id, cron_expression in dict(self._schedule).items():
            if self._is_due(job_id, cron_expression, now):
                self._last_triggered[job_id] = now
                _log.info("Triggering scheduled flow for job %d.", job_id)
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, run_job_flow, job_id)

    def _is_due(self, job_id: int, cron_expression: str, now: datetime) -> bool:
        """Return True if the job has a cron slot in the current poll window."""
        last = self._last_triggered.get(job_id)
        reference = last if last else now.replace(second=0, microsecond=0)
        try:
            cron = croniter(cron_expression, reference.replace(tzinfo=None))
            next_run: datetime = cron.get_next(datetime)
            next_run_utc = next_run.replace(tzinfo=UTC)
            return next_run_utc <= now
        except (ValueError, KeyError):
            _log.warning("Invalid cron expression '%s' for job %d.", cron_expression, job_id)
            return False
