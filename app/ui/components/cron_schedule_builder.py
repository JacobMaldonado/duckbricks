"""Friendly preset and advanced cron controls for the job editor."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import available_timezones

from nicegui import ui

from app.services.jobs.schedule_service import JobScheduleService


class CronScheduleBuilder:
    """Owns schedule controls and exposes a validated cron/timezone pair."""

    MODES = ("Manual", "Hourly", "Daily", "Weekly", "Monthly", "Custom")
    WEEKDAYS = {
        0: "Sunday",
        1: "Monday",
        2: "Tuesday",
        3: "Wednesday",
        4: "Thursday",
        5: "Friday",
        6: "Saturday",
    }

    def __init__(
        self,
        cron_expression: str | None,
        timezone: str,
        *,
        is_enabled: bool,
    ) -> None:
        self._initial_cron = cron_expression
        self._initial_timezone = timezone
        self._initial_enabled = is_enabled
        self._mode = self._mode_for_cron(cron_expression)
        self._mode_select: ui.select | None = None
        self._time_input: ui.input | None = None
        self._minute_input: ui.number | None = None
        self._weekday_select: ui.select | None = None
        self._month_day_input: ui.number | None = None
        self._custom_input: ui.input | None = None
        self._timezone_select: ui.select | None = None
        self._enabled_switch: ui.switch | None = None
        self._dynamic_container: ui.column | None = None
        self._preview_container: ui.column | None = None

    def render(self) -> None:
        with ui.card().classes("w-full q-pa-md gap-3"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.icon("schedule", color="primary")
                with ui.column().classes("gap-0"):
                    ui.label("Schedule").classes("text-subtitle1 text-weight-medium")
                    ui.label("Choose a preset or enter an advanced cron expression.").classes(
                        "text-caption text-grey-6"
                    )
                ui.space()
                self._enabled_switch = ui.switch(
                    "Schedule enabled", value=self._initial_enabled
                ).props("color=primary")

            with ui.row().classes("w-full items-start gap-3"):
                self._mode_select = (
                    ui.select(
                        list(self.MODES),
                        value=self._mode,
                        label="Frequency",
                    )
                    .props("outlined dense")
                    .classes("col")
                )
                self._timezone_select = (
                    ui.select(
                        sorted(available_timezones()),
                        value=self._initial_timezone,
                        label="Timezone",
                    )
                    .props("outlined dense use-input input-debounce=0")
                    .classes("col")
                )

            self._dynamic_container = ui.column().classes("w-full gap-2")
            self._preview_container = ui.column().classes("w-full gap-1")

            self._mode_select.on_value_change(lambda event: self._render_dynamic(event.value))
            self._timezone_select.on_value_change(lambda _: self._refresh_preview())
            self._render_dynamic(self._mode)

    @property
    def cron_expression(self) -> str | None:
        mode = str(self._mode_select.value if self._mode_select else self._mode)
        if mode == "Manual":
            return None
        if mode == "Custom":
            value = str(
                self._custom_input.value if self._custom_input else self._initial_cron or ""
            )
            return value.strip() or None
        minute, hour = self._selected_time()
        if mode == "Hourly":
            minute = int(self._minute_input.value or 0) if self._minute_input else minute
        return JobScheduleService.build_preset(
            mode,
            hour=hour,
            minute=minute,
            weekday=int(self._weekday_select.value or 1) if self._weekday_select else 1,
            month_day=int(self._month_day_input.value or 1) if self._month_day_input else 1,
        )

    @property
    def timezone(self) -> str:
        return str(self._timezone_select.value if self._timezone_select else self._initial_timezone)

    @property
    def is_enabled(self) -> bool:
        return bool(self._enabled_switch.value if self._enabled_switch else self._initial_enabled)

    def _render_dynamic(self, mode: str) -> None:
        if not self._dynamic_container:
            return
        self._dynamic_container.clear()
        with self._dynamic_container:
            if mode == "Manual":
                ui.label("This job will run only when triggered manually.").classes(
                    "text-body2 text-grey-7"
                )
            elif mode == "Hourly":
                self._minute_input = (
                    ui.number("Minute of the hour", value=self._initial_minute(), min=0, max=59)
                    .props("outlined dense")
                    .classes("w-full")
                )
                self._minute_input.on_value_change(lambda _: self._refresh_preview())
            elif mode == "Custom":
                self._custom_input = (
                    ui.input(
                        "Cron expression",
                        value=self._initial_cron or "0 0 * * *",
                        placeholder="0 6 * * *",
                    )
                    .props("outlined dense")
                    .classes("w-full")
                )
                self._custom_input.on_value_change(lambda _: self._refresh_preview())
            else:
                with ui.row().classes("w-full items-start gap-3"):
                    self._time_input = (
                        ui.input("Run at", value=self._initial_time())
                        .props("outlined dense type=time")
                        .classes("col")
                    )
                    if mode == "Weekly":
                        self._weekday_select = (
                            ui.select(
                                self.WEEKDAYS,
                                value=self._initial_weekday(),
                                label="Weekday",
                            )
                            .props("outlined dense map-options emit-value")
                            .classes("col")
                        )
                    if mode == "Monthly":
                        self._month_day_input = (
                            ui.number(
                                "Day of month",
                                value=self._initial_month_day(),
                                min=1,
                                max=31,
                            )
                            .props("outlined dense")
                            .classes("col")
                        )
                self._time_input.on_value_change(lambda _: self._refresh_preview())
                if self._weekday_select:
                    self._weekday_select.on_value_change(lambda _: self._refresh_preview())
                if self._month_day_input:
                    self._month_day_input.on_value_change(lambda _: self._refresh_preview())
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if not self._preview_container:
            return
        self._preview_container.clear()
        with self._preview_container:
            try:
                cron_expression = self.cron_expression
                JobScheduleService.validate(cron_expression, self.timezone)
                ui.label(JobScheduleService.describe(cron_expression, self.timezone)).classes(
                    "text-body2 text-weight-medium"
                )
                runs = JobScheduleService.next_runs(
                    cron_expression,
                    self.timezone,
                    count=3,
                )
                if runs:
                    ui.label("Next: " + " · ".join(self._format_run(run) for run in runs)).classes(
                        "text-caption text-grey-6"
                    )
            except ValueError as exc:
                ui.label(str(exc)).classes("text-caption text-negative")

    def _selected_time(self) -> tuple[int, int]:
        value = str(self._time_input.value if self._time_input else self._initial_time())
        try:
            hour, minute = value.split(":", maxsplit=1)
            return int(minute), int(hour)
        except (ValueError, AttributeError):
            return 0, 0

    def _initial_parts(self) -> tuple[str, str, str, str, str]:
        if self._initial_cron and len(self._initial_cron.split()) == 5:
            return tuple(self._initial_cron.split())  # type: ignore[return-value]
        return "0", "0", "*", "*", "*"

    def _initial_minute(self) -> int:
        minute = self._initial_parts()[0]
        return int(minute) if minute.isdigit() else 0

    def _initial_time(self) -> str:
        minute, hour, *_ = self._initial_parts()
        hour_value = int(hour) if hour.isdigit() else 0
        minute_value = int(minute) if minute.isdigit() else 0
        return f"{hour_value:02d}:{minute_value:02d}"

    def _initial_weekday(self) -> int:
        weekday = self._initial_parts()[4]
        return int(weekday) if weekday.isdigit() else 1

    def _initial_month_day(self) -> int:
        month_day = self._initial_parts()[2]
        return int(month_day) if month_day.isdigit() else 1

    @staticmethod
    def _mode_for_cron(cron_expression: str | None) -> str:
        if not cron_expression:
            return "Manual"
        parts = cron_expression.split()
        if len(parts) != 5:
            return "Custom"
        minute, hour, month_day, month, weekday = parts
        if hour == "*" and (month_day, month, weekday) == ("*", "*", "*"):
            return "Hourly"
        if (month_day, month, weekday) == ("*", "*", "*"):
            return "Daily"
        if (month_day, month) == ("*", "*") and weekday != "*":
            return "Weekly"
        if month == "*" and weekday == "*" and month_day != "*":
            return "Monthly"
        return "Custom"

    @staticmethod
    def _format_run(value: datetime) -> str:
        return value.strftime("%b %d, %H:%M")
