"""Cron validation, descriptions, and preview times for job schedules."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, croniter  # type: ignore[import-untyped]


class JobScheduleValidationError(ValueError):
    """Raised when a cron expression or timezone is invalid."""


class JobScheduleService:
    """Creates and validates the five-field cron schedules supported by the editor."""

    @staticmethod
    def validate(cron_expression: str | None, timezone: str) -> None:
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise JobScheduleValidationError(f"Unknown schedule timezone '{timezone}'.") from exc

        if not cron_expression:
            return
        if len(cron_expression.split()) != 5:
            raise JobScheduleValidationError("Cron schedules must contain exactly five fields.")
        try:
            croniter(cron_expression)
        except (CroniterBadCronError, ValueError, KeyError) as exc:
            raise JobScheduleValidationError(f"Invalid cron schedule: {cron_expression}.") from exc

    @classmethod
    def next_runs(
        cls,
        cron_expression: str | None,
        timezone: str,
        *,
        count: int = 3,
        reference: datetime | None = None,
    ) -> tuple[datetime, ...]:
        cls.validate(cron_expression, timezone)
        if not cron_expression or count <= 0:
            return ()
        zone = ZoneInfo(timezone)
        base = reference.astimezone(zone) if reference else datetime.now(zone)
        iterator = croniter(cron_expression, base)
        return tuple(iterator.get_next(datetime) for _ in range(count))

    @staticmethod
    def build_preset(
        mode: str,
        *,
        hour: int = 0,
        minute: int = 0,
        weekday: int = 1,
        month_day: int = 1,
    ) -> str | None:
        normalized = mode.strip().lower()
        if normalized == "manual":
            return None
        if normalized == "hourly":
            return f"{minute} * * * *"
        if normalized == "daily":
            return f"{minute} {hour} * * *"
        if normalized == "weekly":
            return f"{minute} {hour} * * {weekday}"
        if normalized == "monthly":
            return f"{minute} {hour} {month_day} * *"
        raise JobScheduleValidationError(f"Unknown schedule preset '{mode}'.")

    @staticmethod
    def describe(cron_expression: str | None, timezone: str) -> str:
        if not cron_expression:
            return "Manual only"
        minute, hour, month_day, month, weekday = cron_expression.split()
        suffix = f" · {timezone}"
        if (hour, month_day, month, weekday) == ("*", "*", "*", "*"):
            return f"Hourly at minute {int(minute):02d}{suffix}"
        if (month_day, month, weekday) == ("*", "*", "*"):
            return f"Daily at {int(hour):02d}:{int(minute):02d}{suffix}"
        if (month_day, month) == ("*", "*") and weekday != "*":
            return f"Weekly on day {weekday} at {int(hour):02d}:{int(minute):02d}{suffix}"
        if month == "*" and weekday == "*" and month_day != "*":
            return f"Monthly on day {month_day} at {int(hour):02d}:{int(minute):02d}{suffix}"
        return f"{cron_expression}{suffix}"
