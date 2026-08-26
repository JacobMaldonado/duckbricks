"""Unit tests for timezone-aware job schedules."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.jobs.schedule_service import (
    JobScheduleService,
    JobScheduleValidationError,
)


def test_builds_common_schedule_presets() -> None:
    assert JobScheduleService.build_preset("manual") is None
    assert JobScheduleService.build_preset("hourly", minute=15) == "15 * * * *"
    assert JobScheduleService.build_preset("daily", hour=6, minute=30) == "30 6 * * *"
    assert JobScheduleService.build_preset("weekly", weekday=1, hour=8) == "0 8 * * 1"
    assert JobScheduleService.build_preset("monthly", month_day=5) == "0 0 5 * *"


def test_rejects_invalid_cron_and_timezone() -> None:
    with pytest.raises(JobScheduleValidationError, match="five fields"):
        JobScheduleService.validate("0 0 * * * *", "UTC")
    with pytest.raises(JobScheduleValidationError, match="Unknown"):
        JobScheduleService.validate("0 0 * * *", "Mars/Olympus")


def test_previews_runs_in_the_selected_timezone() -> None:
    zone = ZoneInfo("America/Mexico_City")
    reference = datetime(2026, 8, 25, 7, 0, tzinfo=zone)

    runs = JobScheduleService.next_runs(
        "30 8 * * *",
        "America/Mexico_City",
        count=2,
        reference=reference,
    )

    assert [(run.hour, run.minute) for run in runs] == [(8, 30), (8, 30)]
    assert all(run.tzinfo == zone for run in runs)


def test_describes_daily_and_manual_schedules() -> None:
    assert JobScheduleService.describe(None, "UTC") == "Manual only"
    assert (
        JobScheduleService.describe("30 6 * * *", "America/Mexico_City")
        == "Daily at 06:30 · America/Mexico_City"
    )
