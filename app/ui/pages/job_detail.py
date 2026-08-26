"""Native DuckBricks job definition and Prefect run details."""

from __future__ import annotations

import json
from uuid import UUID

from nicegui import ui

from app.services.database.models.app import Job
from app.services.jobs import JobService, JobTelemetryService
from app.services.jobs.models import JobRunSummary, JobTaskInput, RunLogEntry, TaskRunSummary
from app.services.jobs.schedule_service import JobScheduleService
from app.services.prefect import prefect_client
from app.ui.components.job_flow_diagram import JobFlowDiagram
from app.ui.components.layout import layout_frame
from app.ui.pages.jobs import _STATE_COLORS, JobsDashboard

JOB_DETAIL_CSS = """
<style>
.job-detail-page { min-height: calc(100vh - 64px); background: #fafafa; }
.job-detail-grid { display: grid; grid-template-columns: minmax(300px, .8fr) minmax(0, 1.2fr); }
.job-run-row { border-top: 1px solid #eeeeee; cursor: pointer; }
.job-run-row:hover { background: #fafafa; }
.job-log-view { background: #1e1e1e; color: #eeeeee; border-radius: 4px; min-height: 360px; }
@media (max-width: 850px) { .job-detail-grid { display: flex; flex-direction: column; } }
</style>
"""


class JobDetailPage:
    """Shows one persisted job and loads its execution history from Prefect."""

    def __init__(self, job_service: JobService, telemetry_service: JobTelemetryService) -> None:
        self._job_service = job_service
        self._telemetry_service = telemetry_service
        self._job: Job | None = None
        self._runs_container: ui.column | None = None
        self._latest_container: ui.column | None = None
        self._requested_run_id: UUID | None = None

    def render(self, job_id: int, requested_run: str | None = None) -> None:
        layout_frame("Jobs")
        ui.add_head_html(JOB_DETAIL_CSS)
        self._job = self._job_service.get_job(job_id)
        if not self._job:
            self._render_missing(job_id)
            return
        try:
            self._requested_run_id = UUID(requested_run) if requested_run else None
        except ValueError:
            self._requested_run_id = None

        with ui.column().classes("w-full job-detail-page gap-4 q-pa-lg"):
            self._render_header()
            self._render_definition_summary()
            with ui.card().classes("w-full q-pa-none gap-0"):
                with ui.row().classes("w-full items-center q-pa-md"):
                    with ui.column().classes("gap-0"):
                        ui.label("Recent runs").classes("text-h6 text-weight-medium")
                        ui.label("Execution state is loaded directly from Prefect.").classes(
                            "text-caption text-grey-6"
                        )
                    ui.space()
                    ui.button(icon="refresh", on_click=self._load_runs).props(
                        "flat round color=grey-7 aria-label=Refresh"
                    )
                self._runs_container = ui.column().classes("w-full gap-0")
                self._render_loading_runs()

        ui.timer(0.05, self._load_runs, once=True)

    def _render_header(self) -> None:
        assert self._job is not None
        with ui.row().classes("w-full items-center gap-3"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/jobs")).props(
                "flat round color=grey-7 aria-label=Back"
            )
            with ui.column().classes("gap-0 min-w-0"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(self._job.name).classes("text-h4 text-weight-medium ellipsis")
                    if self._job.schedule_cron:
                        ui.badge(
                            "SCHEDULED" if self._job.is_enabled else "PAUSED",
                            color="positive" if self._job.is_enabled else "grey-6",
                        ).props("outline")
                    else:
                        ui.badge("MANUAL", color="grey-6").props("outline")
                ui.label(self._job.description or "No description").classes(
                    "text-body2 text-grey-6"
                )
            ui.space()
            if self._job.prefect_deployment_id:
                ui.button("Prefect", icon="open_in_new", on_click=self._open_deployment).props(
                    "flat color=grey-7"
                )
            ui.button(
                "Edit",
                icon="edit",
                on_click=lambda: ui.navigate.to(f"/jobs/{self._job.id}/edit"),
            ).props("outline color=primary")
            ui.button("Run now", icon="play_arrow", on_click=self._run_now).props("color=primary")

    def _render_definition_summary(self) -> None:
        assert self._job is not None
        with ui.element("div").classes("w-full job-detail-grid gap-4"):
            with ui.card().classes("w-full q-pa-md gap-4"):
                ui.label("Definition").classes("text-h6 text-weight-medium")
                self._property(
                    "Schedule",
                    JobScheduleService.describe(
                        self._job.schedule_cron,
                        self._job.schedule_timezone,
                    ),
                    "schedule",
                )
                self._property("Tasks", str(len(self._job.tasks)), "account_tree")
                source_count = sum(1 for task in self._job.tasks if task.file_path)
                self._property(
                    "Workspace sources",
                    f"{source_count} of {len(self._job.tasks)} configured",
                    "folder_open",
                )
                self._latest_container = ui.column().classes("w-full gap-1")
                with self._latest_container:
                    self._property("Latest run", "Loading Prefect telemetry…", "sync")
            with ui.card().classes("w-full q-pa-md gap-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("account_tree", color="primary")
                    ui.label("Flow").classes("text-h6 text-weight-medium")
                JobFlowDiagram.render(self._task_inputs(self._job))

    async def _load_runs(self) -> None:
        if not self._job or not self._runs_container:
            return
        try:
            runs = await self._telemetry_service.load_job_runs(self._job)
            requested_run = None
            if self._requested_run_id and all(run.run_id != self._requested_run_id for run in runs):
                requested_run = await self._telemetry_service.load_run(self._requested_run_id)
                runs.insert(0, requested_run)
        except Exception as exc:
            self._render_run_error(str(exc))
            return
        self._render_latest(runs[0] if runs else None)
        self._runs_container.clear()
        with self._runs_container:
            if not runs:
                with ui.column().classes("w-full items-center q-pa-xl gap-2"):
                    ui.icon("history", color="grey-5", size="40px")
                    ui.label("No runs yet").classes("text-grey-7")
                return
            for run in runs:
                self._render_run_row(run)
        if self._requested_run_id:
            selected = next(
                (run for run in runs if run.run_id == self._requested_run_id),
                requested_run,
            )
            self._requested_run_id = None
            if selected:
                await self._open_run(selected)

    def _render_run_row(self, run: JobRunSummary) -> None:
        color = _STATE_COLORS.get(run.state, "grey-6")
        with (
            ui.row()
            .classes("w-full items-center gap-4 q-px-md q-py-sm job-run-row")
            .on("click", lambda current=run: self._open_run(current))
        ):
            ui.icon("circle", color=color, size="12px")
            with ui.column().classes("gap-0 min-w-0"):
                ui.label(run.name).classes("text-body2 text-weight-medium ellipsis")
                ui.label(str(run.run_id)).classes("text-caption text-grey-5 ellipsis")
            ui.badge(run.state.title(), color=color).props("outline")
            ui.space()
            ui.label(
                JobsDashboard._format_datetime(run.started_at) if run.started_at else "Not started"
            ).classes("text-caption text-grey-7")
            ui.label(
                JobsDashboard._format_duration(run.duration_seconds)
                if run.duration_seconds is not None
                else "—"
            ).classes("text-caption text-grey-6").style("min-width: 70px; text-align: right")
            ui.icon("chevron_right", color="grey-5")

    async def _open_run(self, run: JobRunSummary) -> None:
        with (
            ui.dialog().props("maximized") as dialog,
            ui.card().classes("w-full h-full q-pa-none gap-0"),
        ):
            with ui.row().classes("w-full items-center gap-3 q-pa-md border-b"):
                color = _STATE_COLORS.get(run.state, "grey-6")
                ui.icon("circle", color=color, size="14px")
                with ui.column().classes("gap-0"):
                    ui.label(run.name).classes("text-h6")
                    ui.label(str(run.run_id)).classes("text-caption text-grey-6")
                ui.badge(run.state.title(), color=color).props("outline")
                ui.space()
                ui.button(
                    "Open in Prefect",
                    icon="open_in_new",
                    on_click=lambda: self._open_run_url(run),
                ).props("flat color=primary")
                ui.button(icon="close", on_click=dialog.close).props(
                    "flat round color=grey-7 aria-label=Close"
                )

            with ui.tabs().classes("w-full text-grey-7").props("align=left") as tabs:
                tasks_tab = ui.tab("Tasks", icon="account_tree")
                logs_tab = ui.tab("Logs", icon="terminal")
            with ui.tab_panels(tabs, value=tasks_tab).classes("w-full col bg-grey-1"):
                with ui.tab_panel(tasks_tab).classes("q-pa-md"):
                    tasks_container = ui.column().classes("w-full gap-2")
                    with tasks_container:
                        ui.spinner("dots", color="primary", size="32px")
                with ui.tab_panel(logs_tab).classes("q-pa-md"):
                    logs_container = ui.column().classes("w-full gap-2")
                    with logs_container:
                        ui.spinner("dots", color="primary", size="32px")
        dialog.open()

        task_runs, logs = await self._load_run_details(run)
        self._render_task_runs(tasks_container, task_runs)
        self._render_logs(logs_container, logs)

    async def _load_run_details(
        self, run: JobRunSummary
    ) -> tuple[list[TaskRunSummary], list[RunLogEntry]]:
        try:
            task_runs = await self._telemetry_service.load_task_runs(run.run_id)
            logs = await self._telemetry_service.load_logs(run.run_id)
            return task_runs, logs
        except Exception as exc:
            ui.notification(f"Could not load run details: {exc}", type="negative")
            return [], []

    @staticmethod
    def _render_task_runs(container: ui.column, runs: list[TaskRunSummary]) -> None:
        container.clear()
        with container:
            if not runs:
                ui.label("No task runs are available yet.").classes("text-grey-6 q-pa-md")
                return
            for run in runs:
                color = _STATE_COLORS.get(run.state, "grey-6")
                with ui.card().classes("w-full q-pa-md"):
                    with ui.row().classes("w-full items-center gap-3"):
                        ui.icon("circle", color=color, size="12px")
                        with ui.column().classes("gap-0"):
                            ui.label(run.name).classes("text-body1 text-weight-medium")
                            started = (
                                JobsDashboard._format_datetime(run.started_at)
                                if run.started_at
                                else "Not started"
                            )
                            ui.label(started).classes("text-caption text-grey-6")
                        ui.space()
                        ui.badge(run.state.title(), color=color).props("outline")
                        ui.label(
                            JobsDashboard._format_duration(run.duration_seconds)
                            if run.duration_seconds is not None
                            else "—"
                        ).classes("text-caption text-grey-7")

    @staticmethod
    def _render_logs(container: ui.column, logs: list[RunLogEntry]) -> None:
        container.clear()
        with container:
            if not logs:
                ui.label("No logs are available yet.").classes("text-grey-6 q-pa-md")
                return
            log_view = ui.log(max_lines=500).classes("w-full job-log-view q-pa-sm")
            for entry in logs:
                timestamp = entry.timestamp.astimezone().strftime("%H:%M:%S")
                log_view.push(f"{timestamp}  {entry.message}")

    def _render_latest(self, run: JobRunSummary | None) -> None:
        if not self._latest_container:
            return
        self._latest_container.clear()
        with self._latest_container:
            if not run:
                self._property("Latest run", "No runs yet", "history")
                return
            value = run.state.title()
            if run.started_at:
                value += f" · {JobsDashboard._relative_time(run.started_at)}"
            self._property("Latest run", value, "history")

    def _render_loading_runs(self) -> None:
        if not self._runs_container:
            return
        with self._runs_container:
            with ui.column().classes("w-full items-center q-pa-lg"):
                ui.spinner("dots", color="primary", size="32px")

    def _render_run_error(self, message: str) -> None:
        self._render_latest(None)
        if not self._runs_container:
            return
        self._runs_container.clear()
        with self._runs_container:
            with ui.column().classes("w-full items-center q-pa-lg gap-2"):
                ui.icon("cloud_off", color="orange-8", size="36px")
                ui.label("Prefect telemetry is unavailable").classes("text-orange-9")
                ui.label(message).classes("text-caption text-grey-6 text-center")

    def _run_now(self) -> None:
        assert self._job is not None
        try:
            run = self._job_service.run_job(self._job.id)
        except Exception as exc:
            ui.notification(f"Could not trigger job: {exc}", type="negative")
            return
        ui.notification(f"Run '{run.name}' was scheduled.", type="positive")
        self._requested_run_id = run.id
        ui.timer(1, self._load_runs, once=True)

    def _open_deployment(self) -> None:
        assert self._job is not None
        if not self._job.prefect_deployment_id:
            return
        url = prefect_client.deployment_ui_url(UUID(self._job.prefect_deployment_id))
        ui.run_javascript(f"window.open({json.dumps(url)}, '_blank')")

    @staticmethod
    def _open_run_url(run: JobRunSummary) -> None:
        url = prefect_client.run_ui_url(run.run_id)
        ui.run_javascript(f"window.open({json.dumps(url)}, '_blank')")

    @staticmethod
    def _task_inputs(job: Job) -> tuple[JobTaskInput, ...]:
        key_by_id = {task.id: f"task-{task.id}" for task in job.tasks}
        return tuple(
            JobTaskInput(
                key=key_by_id[task.id],
                task_id=task.id,
                name=task.name,
                file_path=task.file_path,
                executor_type=task.executor_type,
                depends_on=tuple(
                    key_by_id[edge.depends_on_task_id]
                    for edge in task.dependency_edges
                    if edge.depends_on_task_id in key_by_id
                ),
                legacy_content=task.content,
            )
            for task in sorted(job.tasks, key=lambda item: item.position)
        )

    @staticmethod
    def _property(label: str, value: str, icon: str) -> None:
        with ui.row().classes("w-full items-start gap-3"):
            ui.icon(icon, color="grey-6", size="20px")
            with ui.column().classes("gap-0 min-w-0"):
                ui.label(label).classes("text-caption text-grey-6")
                ui.label(value).classes("text-body2 text-grey-9").style("word-break: break-word")

    @staticmethod
    def _render_missing(job_id: int) -> None:
        with ui.column().classes("w-full items-center justify-center q-pa-xl gap-3"):
            ui.icon("error_outline", color="negative", size="44px")
            ui.label(f"Job {job_id} was not found.").classes("text-h6")
            ui.button("Back to jobs", on_click=lambda: ui.navigate.to("/jobs")).props(
                "color=primary"
            )


def job_detail_page(job_id: int, requested_run: str | None = None) -> None:
    """Render a job definition and native Prefect run history."""
    JobDetailPage(JobService(), JobTelemetryService(prefect_client)).render(
        job_id,
        requested_run,
    )
