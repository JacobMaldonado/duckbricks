"""Unit tests for PrefectJobScheduler."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.jobs.scheduler import PrefectJobScheduler


class TestPrefectJobSchedulerScheduleManagement:
    def setup_method(self):
        self.scheduler = PrefectJobScheduler()

    def test_schedule_job_registers_cron_expression(self):
        self.scheduler.schedule_job(1, "0 * * * *")
        assert self.scheduler._schedule[1] == "0 * * * *"

    def test_schedule_job_is_idempotent(self):
        self.scheduler.schedule_job(1, "0 * * * *")
        self.scheduler.schedule_job(1, "*/5 * * * *")
        assert self.scheduler._schedule[1] == "*/5 * * * *"

    def test_unschedule_job_removes_entry(self):
        self.scheduler.schedule_job(1, "0 * * * *")
        self.scheduler.unschedule_job(1)
        assert 1 not in self.scheduler._schedule

    def test_unschedule_job_clears_last_triggered(self):
        self.scheduler._schedule[1] = "0 * * * *"
        self.scheduler._last_triggered[1] = datetime.now(UTC)
        self.scheduler.unschedule_job(1)
        assert 1 not in self.scheduler._last_triggered

    def test_unschedule_nonexistent_job_does_not_raise(self):
        self.scheduler.unschedule_job(999)

    def test_reschedule_job_updates_expression_and_clears_last_triggered(self):
        self.scheduler.schedule_job(2, "0 * * * *")
        self.scheduler._last_triggered[2] = datetime.now(UTC)
        self.scheduler.reschedule_job(2, "30 * * * *")
        assert self.scheduler._schedule[2] == "30 * * * *"
        assert 2 not in self.scheduler._last_triggered


class TestPrefectJobSchedulerIsDue:
    def setup_method(self):
        self.scheduler = PrefectJobScheduler()

    def test_job_is_due_when_next_run_has_passed(self):
        two_minutes_ago = datetime.now(UTC) - timedelta(minutes=2)
        self.scheduler._last_triggered[1] = two_minutes_ago
        assert self.scheduler._is_due(1, "* * * * *", datetime.now(UTC)) is True

    def test_job_is_not_due_when_next_run_is_in_the_future(self):
        just_triggered = datetime.now(UTC) - timedelta(seconds=5)
        self.scheduler._last_triggered[1] = just_triggered
        future_now = datetime.now(UTC)
        assert self.scheduler._is_due(1, "0 2 * * *", future_now) is False

    def test_invalid_cron_expression_returns_false(self):
        now = datetime.now(UTC)
        result = self.scheduler._is_due(1, "not-a-cron", now)
        assert result is False

    def test_job_without_last_triggered_uses_current_time_as_reference(self):
        now = datetime.now(UTC)
        result = self.scheduler._is_due(99, "* * * * *", now)
        assert isinstance(result, bool)


class TestPrefectJobSchedulerSyncFromDatabase:
    def setup_method(self):
        self.scheduler = PrefectJobScheduler()

    def test_sync_registers_enabled_jobs_with_cron(self):
        enabled_job = MagicMock(id=1, is_enabled=True, schedule_cron="0 0 * * *")
        disabled_job = MagicMock(id=2, is_enabled=False, schedule_cron="0 0 * * *")
        no_cron_job = MagicMock(id=3, is_enabled=True, schedule_cron=None)

        with patch("app.services.jobs.job_service.JobService") as MockService:
            MockService.return_value.list_jobs.return_value = [
                enabled_job,
                disabled_job,
                no_cron_job,
            ]
            self.scheduler.sync_from_database()

        assert self.scheduler._schedule == {1: "0 0 * * *"}
        assert 2 not in self.scheduler._schedule
        assert 3 not in self.scheduler._schedule

    def test_sync_clears_previous_schedule(self):
        self.scheduler._schedule = {10: "* * * * *", 11: "0 0 * * *"}
        with patch("app.services.jobs.job_service.JobService") as MockService:
            MockService.return_value.list_jobs.return_value = []
            self.scheduler.sync_from_database()
            assert self.scheduler._schedule == {}


class TestPrefectJobSchedulerStartShutdown:
    def test_start_creates_loop_task(self):
        scheduler = PrefectJobScheduler()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_start_and_verify(scheduler))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def test_shutdown_cancels_task(self):
        scheduler = PrefectJobScheduler()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_start_and_shutdown(scheduler))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def test_start_is_idempotent(self):
        scheduler = PrefectJobScheduler()
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_start_twice(scheduler))
        finally:
            loop.close()
            asyncio.set_event_loop(None)


async def _start_and_verify(scheduler: PrefectJobScheduler) -> None:
    scheduler.start()
    assert scheduler._loop_task is not None
    assert not scheduler._loop_task.done()
    scheduler.shutdown()
    await asyncio.sleep(0)


async def _start_and_shutdown(scheduler: PrefectJobScheduler) -> None:
    scheduler.start()
    task = scheduler._loop_task
    scheduler.shutdown()
    await asyncio.sleep(0)
    assert scheduler._loop_task is None
    assert task.cancelled() or task.done()


async def _start_twice(scheduler: PrefectJobScheduler) -> None:
    scheduler.start()
    first_task = scheduler._loop_task
    scheduler.start()
    assert scheduler._loop_task is first_task
    scheduler.shutdown()
    await asyncio.sleep(0)
