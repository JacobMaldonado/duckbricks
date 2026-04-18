"""Job Execution Detail page — per-task stage view with timing and output inspection."""

from datetime import UTC, datetime

from nicegui import ui

from app.services.jobs import JobService
from app.ui.components.layout import layout_frame

_job_service = JobService()

_STATUS_ICON = {
    "success": ("check_circle", "green"),
    "failed": ("cancel", "red"),
    "running": ("pending", "blue"),
    "pending": ("radio_button_unchecked", "grey"),
    "cancelled": ("do_not_disturb", "grey"),
}


def _human_duration(duration_ms: int | None) -> str:
    if duration_ms is None:
        return "—"
    if duration_ms < 1000:
        return f"{duration_ms} ms"
    return f"{duration_ms / 1000:.1f} s"


def _format_datetime(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _elapsed_since(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    now = datetime.now(UTC)
    aware = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    elapsed_ms = int((now - aware).total_seconds() * 1000)
    return f"{_human_duration(elapsed_ms)} (running)"


def job_execution_page(execution_id: int) -> None:
    """Render the job execution detail page."""
    layout_frame("Job Execution")

    container = ui.column().classes("w-full h-full p-4 gap-4")
    _render_execution(execution_id, container)


def _render_execution(execution_id: int, container: ui.column) -> None:
    container.clear()

    execution = _job_service.get_execution(execution_id)

    if execution is None:
        with container:
            with ui.card().classes("w-full"):
                ui.label(f"Execution #{execution_id} not found.").classes(
                    "text-grey-6 text-center q-pa-lg"
                )
        return

    with container:
        _render_header(execution, execution_id, container)
        _render_task_list(execution)

    if execution["status"] == "running":
        timer = ui.timer(
            2.0,
            lambda: _refresh_if_running(execution_id, container, timer),
        )


def _refresh_if_running(execution_id: int, container: ui.column, timer: ui.timer) -> None:
    execution = _job_service.get_execution(execution_id)
    if execution is None or execution["status"] != "running":
        timer.cancel()
    _render_execution(execution_id, container)


def _render_header(execution: dict, execution_id: int, container: ui.column) -> None:
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/jobs"),
                ).props("flat dense color=grey").tooltip("Back to Jobs")
                ui.label(execution["job_name"]).classes("text-h6 text-weight-bold")
                ui.label(f"Run #{execution_id}").classes("text-caption text-grey-6")

            with ui.row().classes("items-center gap-2"):
                _render_status_chip(execution["status"])
                ui.button(
                    "Re-run",
                    icon="replay",
                    on_click=lambda: _rerun_job(execution["job_id"]),
                ).props("flat color=primary")

        ui.separator()

        with ui.row().classes("gap-6 q-pt-sm flex-wrap"):
            _info_cell("Started", _format_datetime(execution["started_at"]))
            _info_cell(
                "Finished",
                _format_datetime(execution["completed_at"])
                if execution["status"] != "running"
                else _elapsed_since(execution["started_at"]),
            )
            _info_cell("Total duration", _human_duration(execution["duration_ms"]))
            _info_cell("Tasks", str(len(execution["task_executions"])))


def _info_cell(label: str, value: str) -> None:
    with ui.column().classes("gap-0"):
        ui.label(label).classes("text-caption text-grey-6")
        ui.label(value).classes("text-body2 text-weight-medium")


def _render_status_chip(status: str) -> None:
    icon, color = _STATUS_ICON.get(status, ("help", "grey"))
    with ui.row().classes(f"items-center gap-1 text-{color}"):
        ui.icon(icon).classes(f"text-{color}")
        ui.label(status.upper()).classes(f"text-caption text-weight-bold text-{color}")


def _render_task_list(execution: dict) -> None:
    ui.label("Tasks").classes("text-subtitle1 text-weight-bold")

    tasks = execution["task_executions"]
    if not tasks:
        with ui.card().classes("w-full"):
            ui.label("No tasks recorded for this execution.").classes("text-grey-6 q-pa-md")
        return

    for task in tasks:
        _render_task_card(task)


def _render_task_card(task: dict) -> None:
    icon, color = _STATUS_ICON.get(task["status"], ("help", "grey"))
    has_detail = bool(task.get("output") or task.get("error_message"))

    duration_label = (
        _elapsed_since(task["started_at"])
        if task["status"] == "running"
        else _human_duration(task["duration_ms"])
    )

    header_text = f"{task['task_name']}  ·  {task['executor_type']}  ·  {duration_label}"

    with ui.expansion(header_text, icon=icon).classes(
        f"w-full border-l-4 border-{color} q-mb-sm"
    ) as expansion:
        expansion.props(f'header-class="text-{color} text-weight-medium"')

        if not has_detail:
            ui.label("No output recorded.").classes("text-grey-6 text-caption q-pa-sm")
            return

        if task.get("error_message"):
            ui.label("Error").classes("text-weight-bold text-red q-mb-xs")
            ui.code(task["error_message"], language="text").classes("w-full text-caption")

        if task.get("output") and not task.get("error_message"):
            ui.label("Output").classes("text-weight-bold text-grey-8 q-mb-xs")
            ui.code(task["output"], language="text").classes("w-full text-caption")


def _rerun_job(job_id: int) -> None:
    try:
        new_execution = _job_service.run_job(job_id)
        ui.navigate.to(f"/jobs/execution/{new_execution.id}")
    except Exception as exc:
        ui.notification(f"Re-run failed: {exc}", type="negative")
