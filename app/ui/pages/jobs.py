"""Prefect-backed Jobs operations dashboard."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from nicegui import ui
from sqlalchemy.exc import OperationalError

from app.services.database.connection import DatabaseConnection
from app.services.database.models.app import Job
from app.services.jobs import JobService, JobTelemetryService
from app.services.jobs.models import JobRunSummary, JobTelemetry
from app.services.jobs.schedule_service import JobScheduleService
from app.services.prefect import prefect_client
from app.ui.components.layout import layout_frame

JOBS_DASHBOARD_CSS = """
<style>
.jobs-page { min-height: calc(100vh - 64px); background: #fafafa; }
.jobs-kpis { display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); }
.jobs-table-header,
.jobs-row {
    display: grid;
    grid-template-columns: minmax(220px, 1.7fr) minmax(190px, 1.25fr) 90px
                           minmax(175px, 1.15fr) minmax(150px, 1fr) 150px;
    align-items: center;
    gap: 16px;
}
.jobs-table-header { color: #757575; font-size: 12px; font-weight: 500; }
.jobs-row { background: white; border-top: 1px solid #eeeeee; min-height: 88px; }
.jobs-row:hover { background: #fafafa; }
.jobs-state-dot { width: 9px; height: 9px; border-radius: 50%; flex: 0 0 9px; }
@media (max-width: 1100px) {
    .jobs-table-header { display: none; }
    .jobs-row { grid-template-columns: minmax(220px, 1.5fr) minmax(180px, 1fr) 100px 150px; }
    .jobs-last-run { grid-column: 1 / 3; }
    .jobs-next-run { grid-column: 3; }
    .jobs-actions { grid-column: 4; grid-row: 1 / 3; }
}
@media (max-width: 720px) {
    .jobs-kpis { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
    .jobs-row { display: flex; flex-direction: column; align-items: stretch; gap: 12px; }
    .jobs-actions { align-self: flex-end; }
}
</style>
"""

_STATE_COLORS: dict[str, str] = {
    "COMPLETED": "positive",
    "FAILED": "negative",
    "CRASHED": "negative",
    "RUNNING": "primary",
    "SCHEDULED": "orange",
    "PENDING": "orange",
    "CANCELLED": "grey-6",
    "CANCELLING": "grey-6",
    "PAUSED": "grey-6",
    "UNKNOWN": "grey-5",
}


class JobsDashboard:
    """Renders job definitions immediately and enriches them with Prefect telemetry."""

    def __init__(self, job_service: JobService, telemetry_service: JobTelemetryService) -> None:
        self._job_service = job_service
        self._telemetry_service = telemetry_service
        self._jobs: list[Job] = []
        self._telemetry: dict[int, JobTelemetry] = {}
        self._telemetry_error: str | None = None
        self._summary_container: ui.column | None = None
        self._rows_container: ui.column | None = None
        self._search = ""
        self._status_filter = "All"

    def render(self) -> None:
        layout_frame("Jobs")
        ui.add_head_html(JOBS_DASHBOARD_CSS)
        with ui.column().classes("w-full jobs-page gap-4 q-pa-lg"):
            database_unavailable = (
                not DatabaseConnection.is_available()
                and not DatabaseConnection.check_connectivity()
            )
            if database_unavailable:
                self._render_db_unavailable_banner()
                return
            try:
                self._jobs = self._job_service.list_jobs()
            except OperationalError:
                self._render_db_unavailable_banner()
                return

            self._render_header()
            self._summary_container = ui.column().classes("w-full")
            self._render_summary()
            self._render_filters()
            with ui.card().classes("w-full q-pa-none gap-0"):
                with ui.element("div").classes("jobs-table-header q-px-md q-py-sm"):
                    for label in ("JOB", "SCHEDULE", "TASKS", "LAST RUN", "NEXT RUN", ""):
                        ui.label(label)
                self._rows_container = ui.column().classes("w-full gap-0")
                self._render_rows()

        if self._jobs:
            ui.timer(0.05, self._refresh_telemetry, once=True)
            ui.timer(30, self._refresh_telemetry)

    def _render_header(self) -> None:
        with ui.row().classes("w-full items-end gap-3"):
            with ui.column().classes("gap-0"):
                ui.label("Jobs").classes("text-h4 text-weight-medium")
                ui.label("Build, schedule, and monitor Prefect-backed pipelines.").classes(
                    "text-body2 text-grey-6"
                )
            ui.space()
            ui.button(
                "New job",
                icon="add",
                on_click=lambda: ui.navigate.to("/jobs/new"),
            ).props("color=primary")

    def _render_filters(self) -> None:
        with ui.row().classes("w-full items-center gap-3"):
            search = (
                ui.input(placeholder="Search jobs...")
                .props("outlined dense clearable prepend-icon=search")
                .style("min-width: 280px")
            )
            status = (
                ui.select(
                    ["All", "Scheduled", "Manual", "Running", "Failed", "Paused"],
                    value="All",
                    label="Status",
                )
                .props("outlined dense")
                .style("min-width: 160px")
            )
            ui.space()
            if self._telemetry_error:
                with ui.row().classes("items-center gap-1"):
                    ui.icon("cloud_off", color="orange-8", size="18px")
                    ui.label("Prefect telemetry unavailable").classes(
                        "text-caption text-orange-9"
                    ).tooltip(self._telemetry_error)
            ui.button(icon="refresh", on_click=self._refresh_telemetry).props(
                "flat round color=grey-7 aria-label=Refresh"
            ).tooltip("Refresh telemetry")

        def apply_search(event) -> None:
            self._search = str(event.value or "").strip().casefold()
            self._render_rows()

        def apply_status(event) -> None:
            self._status_filter = str(event.value or "All")
            self._render_rows()

        search.on_value_change(apply_search)
        status.on_value_change(apply_status)

    def _render_summary(self) -> None:
        if not self._summary_container:
            return
        self._summary_container.clear()
        with self._summary_container:
            with ui.element("div").classes("w-full jobs-kpis gap-3"):
                self._metric("Total jobs", str(len(self._jobs)), "account_tree", "primary")
                scheduled = sum(1 for job in self._jobs if job.schedule_cron and job.is_enabled)
                self._metric("Active schedules", str(scheduled), "event_repeat", "teal")
                if self._telemetry_error or not self._telemetry:
                    self._metric("Running now", "—", "play_circle", "grey-6")
                    self._metric("Success · 7 days", "—", "verified", "grey-6")
                    return
                recent_runs = [
                    run for telemetry in self._telemetry.values() for run in telemetry.recent_runs
                ]
                running = sum(1 for run in recent_runs if run.state in {"RUNNING", "PENDING"})
                self._metric("Running now", str(running), "play_circle", "primary")
                self._metric(
                    "Success · 7 days",
                    self._success_rate(recent_runs),
                    "verified",
                    "positive",
                )

    def _render_rows(self) -> None:
        if not self._rows_container:
            return
        self._rows_container.clear()
        jobs = [job for job in self._jobs if self._matches_filters(job)]
        with self._rows_container:
            if not jobs:
                with ui.column().classes("w-full items-center q-pa-xl gap-2"):
                    ui.icon("work_off", color="grey-5", size="42px")
                    ui.label(
                        "No jobs match these filters." if self._jobs else "No jobs yet"
                    ).classes("text-subtitle1 text-grey-7")
                    if not self._jobs:
                        ui.button(
                            "Create your first job",
                            icon="add",
                            on_click=lambda: ui.navigate.to("/jobs/new"),
                        ).props("outline color=primary")
                return
            for job in jobs:
                self._render_job_row(job)

    def _render_job_row(self, job: Job) -> None:
        telemetry = self._telemetry.get(job.id, JobTelemetry())
        with ui.element("div").classes("jobs-row q-pa-md"):
            with ui.column().classes("gap-1 min-w-0"):
                ui.link(job.name, f"/jobs/{job.id}").classes(
                    "text-body1 text-weight-medium text-grey-9 ellipsis"
                )
                ui.label(job.description or "No description").classes(
                    "text-caption text-grey-6 ellipsis"
                )
            with ui.column().classes("gap-1 min-w-0"):
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.icon("schedule", color="grey-6", size="18px")
                    ui.label(
                        JobScheduleService.describe(job.schedule_cron, job.schedule_timezone)
                    ).classes("text-body2 ellipsis")
                if job.schedule_cron:
                    label = "Enabled" if job.is_enabled else "Paused"
                    color = "positive" if job.is_enabled else "grey-6"
                    ui.badge(label, color=color).props("outline")
            with ui.column().classes("gap-0"):
                ui.label(str(len(job.tasks))).classes("text-body1 text-weight-medium")
                missing = sum(1 for task in job.tasks if not task.file_path)
                ui.label(f"{missing} missing" if missing else "Workspace").classes(
                    f"text-caption {'text-negative' if missing else 'text-grey-6'}"
                )
            with ui.column().classes("gap-1 jobs-last-run"):
                self._render_run_state(telemetry.latest_run)
            with ui.column().classes("gap-1 jobs-next-run"):
                if telemetry.next_run and telemetry.next_run.expected_start_time:
                    ui.label(self._format_datetime(telemetry.next_run.expected_start_time)).classes(
                        "text-body2"
                    )
                    ui.label(self._relative_time(telemetry.next_run.expected_start_time)).classes(
                        "text-caption text-grey-6"
                    )
                else:
                    ui.label("—").classes("text-body2 text-grey-6")
                    ui.label("Manual or paused").classes("text-caption text-grey-6")
            with ui.row().classes("items-center justify-end gap-1 jobs-actions"):
                ui.button(
                    icon="play_arrow", on_click=lambda current=job: self._run_now(current)
                ).props("flat round color=primary aria-label=Run").tooltip("Run now")
                ui.button(
                    icon="edit",
                    on_click=lambda current=job: ui.navigate.to(f"/jobs/{current.id}/edit"),
                ).props("flat round color=grey-7 aria-label=Edit").tooltip("Edit")
                with ui.button(icon="more_vert").props("flat round color=grey-7 aria-label=More"):
                    with ui.menu():
                        ui.menu_item(
                            "View details",
                            on_click=lambda current=job: ui.navigate.to(f"/jobs/{current.id}"),
                        )
                        if job.schedule_cron:
                            ui.menu_item(
                                "Pause schedule" if job.is_enabled else "Resume schedule",
                                on_click=lambda current=job: self._toggle_enabled(current),
                            )
                        if job.prefect_deployment_id:
                            ui.menu_item(
                                "Open in Prefect",
                                on_click=lambda current=job: self._open_prefect(current),
                            )
                        ui.separator()
                        ui.menu_item(
                            "Delete job",
                            on_click=lambda current=job: self._confirm_delete(current),
                        ).classes("text-negative")

    def _render_run_state(self, run: JobRunSummary | None) -> None:
        if not run:
            ui.label("No runs yet").classes("text-body2 text-grey-6")
            ui.label("—").classes("text-caption text-grey-6")
            return
        color = _STATE_COLORS.get(run.state, "grey-6")
        with ui.row().classes("items-center gap-2"):
            ui.element("span").classes(f"jobs-state-dot bg-{color}")
            ui.label(run.state.title()).classes(f"text-body2 text-{color}")
        detail = self._relative_time(run.started_at) if run.started_at else "Not started"
        if run.duration_seconds is not None:
            detail += f" · {self._format_duration(run.duration_seconds)}"
        ui.label(detail).classes("text-caption text-grey-6")

    async def _refresh_telemetry(self) -> None:
        try:
            self._telemetry = await self._telemetry_service.load_dashboard(self._jobs)
            self._telemetry_error = None
        except Exception as exc:
            self._telemetry_error = str(exc)
        self._render_summary()
        self._render_rows()

    def _run_now(self, job: Job) -> None:
        notification = ui.notification(f"Triggering '{job.name}'...", type="ongoing", timeout=None)
        try:
            flow_run = self._job_service.run_job(job.id)
        except Exception as exc:
            notification.dismiss()
            ui.notification(f"Could not trigger job: {exc}", type="negative")
            return
        notification.dismiss()
        ui.notification(f"Run '{flow_run.name}' was scheduled.", type="positive")
        ui.navigate.to(f"/jobs/{job.id}?run={flow_run.id}")

    def _toggle_enabled(self, job: Job) -> None:
        try:
            updated = self._job_service.toggle_enabled(job.id)
        except Exception as exc:
            ui.notification(f"Could not update schedule: {exc}", type="negative")
            return
        if updated:
            state = "resumed" if updated.is_enabled else "paused"
            ui.notification(f"Schedule {state}.", type="positive")
            self._jobs = self._job_service.list_jobs()
            self._render_summary()
            self._render_rows()

    def _open_prefect(self, job: Job) -> None:
        if not job.prefect_deployment_id:
            return
        url = prefect_client.deployment_ui_url(UUID(job.prefect_deployment_id))
        ui.run_javascript(f"window.open({json.dumps(url)}, '_blank')")

    def _confirm_delete(self, job: Job) -> None:
        with ui.dialog() as dialog, ui.card().classes("q-pa-md").style("min-width: 420px"):
            ui.label(f"Delete '{job.name}'?").classes("text-h6")
            ui.label(
                "The DuckBricks definition and its Prefect deployment will be removed."
            ).classes("text-body2 text-grey-7")
            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                def delete() -> None:
                    self._job_service.delete_job(job.id)
                    self._jobs = [candidate for candidate in self._jobs if candidate.id != job.id]
                    dialog.close()
                    self._render_summary()
                    self._render_rows()
                    ui.notification(f"Job '{job.name}' deleted.", type="positive")

                ui.button("Delete", icon="delete", on_click=delete).props("color=negative")
        dialog.open()

    def _matches_filters(self, job: Job) -> bool:
        searchable = f"{job.name} {job.description or ''}".casefold()
        if self._search and self._search not in searchable:
            return False
        telemetry = self._telemetry.get(job.id, JobTelemetry())
        latest_state = telemetry.latest_run.state if telemetry.latest_run else ""
        return {
            "All": True,
            "Scheduled": bool(job.schedule_cron and job.is_enabled),
            "Manual": not job.schedule_cron,
            "Running": latest_state in {"RUNNING", "PENDING"},
            "Failed": latest_state in {"FAILED", "CRASHED"},
            "Paused": bool(job.schedule_cron and not job.is_enabled),
        }.get(self._status_filter, True)

    @staticmethod
    def _metric(label: str, value: str, icon: str, color: str) -> None:
        with ui.card().classes("q-pa-md"):
            with ui.row().classes("items-center gap-3 no-wrap"):
                ui.icon(icon, color=color, size="28px")
                with ui.column().classes("gap-0"):
                    ui.label(label).classes("text-caption text-grey-6")
                    ui.label(value).classes("text-h5 text-weight-medium")

    @staticmethod
    def _success_rate(runs: list[JobRunSummary]) -> str:
        cutoff = datetime.now(UTC) - timedelta(days=7)
        terminal = [
            run
            for run in runs
            if run.state in {"COMPLETED", "FAILED", "CRASHED", "CANCELLED"}
            and run.started_at
            and JobsDashboard._as_aware(run.started_at) >= cutoff
        ]
        if not terminal:
            return "—"
        completed = sum(1 for run in terminal if run.state == "COMPLETED")
        return f"{completed / len(terminal):.0%}"

    @staticmethod
    def _relative_time(value: datetime | None) -> str:
        if value is None:
            return "—"
        delta = JobsDashboard._as_aware(value) - datetime.now(UTC)
        future = delta.total_seconds() > 0
        seconds = abs(int(delta.total_seconds()))
        if seconds < 60:
            amount = "moments"
        elif seconds < 3600:
            amount = f"{seconds // 60}m"
        elif seconds < 86400:
            amount = f"{seconds // 3600}h"
        else:
            amount = f"{seconds // 86400}d"
        return f"in {amount}" if future else f"{amount} ago"

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.astimezone().strftime("%b %d, %H:%M")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        minutes, remainder = divmod(int(seconds), 60)
        if minutes < 60:
            return f"{minutes}m {remainder}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m"

    @staticmethod
    def _as_aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _render_db_unavailable_banner() -> None:
        with ui.card().classes("w-full bg-orange-1 border-orange"):
            with ui.row().classes("items-center gap-3 q-pa-md"):
                ui.icon("warning", color="orange")
                with ui.column().classes("gap-0"):
                    ui.label("PostgreSQL not available").classes("text-weight-bold text-orange-9")
                    ui.label("Jobs require the DuckBricks application database.").classes(
                        "text-caption text-grey-7"
                    )


def jobs_page() -> None:
    """Render the Jobs operations dashboard."""
    JobsDashboard(JobService(), JobTelemetryService(prefect_client)).render()
