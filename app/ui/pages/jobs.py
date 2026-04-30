"""Jobs page — create, manage, and monitor scheduled DuckBricks jobs."""

from pathlib import Path
from uuid import UUID

from nicegui import ui
from prefect.client.schemas.objects import FlowRun
from sqlalchemy.exc import OperationalError

from app.config import PREFECT_UI_BASE_PATH, WORKSPACE_PATH
from app.services.database.connection import DatabaseConnection
from app.services.database.models.app import Job
from app.services.jobs import JobService
from app.services.prefect import prefect_client
from app.ui.components.layout import layout_frame

_job_service = JobService()

_STATE_COLORS: dict[str, str] = {
    "COMPLETED": "green",
    "FAILED": "red",
    "CRASHED": "red",
    "RUNNING": "blue",
    "SCHEDULED": "orange",
    "PENDING": "orange",
    "CANCELLED": "grey",
    "CANCELLING": "grey",
    "PAUSED": "grey",
}


def _list_workspace_files(extensions: list[str]) -> list[str]:
    """Return absolute paths of workspace files matching the given extensions."""
    root = Path(WORKSPACE_PATH)
    if not root.exists():
        return []
    return sorted(str(p) for ext in extensions for p in root.rglob(f"*.{ext}"))


def jobs_page() -> None:
    """Render the Jobs management page."""
    layout_frame("Jobs")

    with ui.column().classes("w-full h-full p-4 gap-4"):
        if not DatabaseConnection.is_available() and not DatabaseConnection.check_connectivity():
            _render_db_unavailable_banner()
            return
        _render_page_header()
        jobs_container = ui.column().classes("w-full gap-2")
        _render_jobs_list(jobs_container)


def _render_db_unavailable_banner() -> None:
    with ui.card().classes("w-full bg-orange-1 border-orange"):
        with ui.row().classes("items-center gap-3 q-pa-md"):
            ui.icon("warning", color="orange").classes("text-h5")
            with ui.column().classes("gap-1"):
                ui.label("PostgreSQL not available").classes("text-weight-bold text-orange-9")
                ui.label(
                    "The Jobs feature requires a running PostgreSQL database. "
                    "Start the full stack with docker compose up, or set DATABASE_URL in your .env."
                ).classes("text-caption text-grey-7")


def _render_page_header() -> None:
    with ui.row().classes("w-full items-center justify-between"):
        ui.label("Jobs").classes("text-h5 text-weight-bold")
        ui.button("+ New Job", on_click=lambda: _open_job_dialog(None, None)).props("color=primary")


def _render_jobs_list(container: ui.column) -> None:
    container.clear()
    try:
        jobs = _job_service.list_jobs()
    except OperationalError:
        with container:
            _render_db_unavailable_banner()
        return

    if not jobs:
        with container:
            with ui.card().classes("w-full"):
                ui.label("No jobs yet. Click '+ New Job' to create your first job.").classes(
                    "text-grey-6 text-center q-pa-lg"
                )
        return

    with container:
        for job in jobs:
            _render_job_row(job, container)


def _render_job_row(job: Job, jobs_container: ui.column) -> None:
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-1"):
                ui.label(job.name).classes("text-weight-bold text-body1")
                if job.description:
                    ui.label(job.description).classes("text-grey-7 text-caption")
                schedule_label = job.schedule_cron if job.schedule_cron else "Manual only"
                ui.label(f"Schedule: {schedule_label}").classes("text-caption text-grey-6")

            with ui.row().classes("items-center gap-2"):
                status_icon = "check_circle" if job.is_enabled else "pause_circle"
                status_color = "green" if job.is_enabled else "grey"
                status_tooltip = "Disable schedule" if job.is_enabled else "Enable schedule"
                ui.button(
                    icon=status_icon,
                    on_click=lambda j=job, c=jobs_container: _toggle_job_enabled(j, c),
                ).props(f"flat dense color={status_color}").tooltip(status_tooltip)

                ui.button(
                    icon="play_arrow",
                    on_click=lambda j=job, c=jobs_container: _run_job_now(j, c),
                ).props("flat dense color=primary").tooltip("Run now")
                ui.button(
                    icon="history",
                    on_click=lambda j=job: _open_run_history(j),
                ).props("flat dense color=grey").tooltip("View run history")
                ui.button(
                    icon="open_in_new",
                    on_click=lambda j=job: _open_deployment_details(j),
                ).props("flat dense color=grey").tooltip("Deployment details in Prefect")
                ui.button(
                    icon="edit",
                    on_click=lambda j=job, c=jobs_container: _open_job_dialog(j, c),
                ).props("flat dense color=grey").tooltip("Edit job")
                ui.button(
                    icon="delete",
                    on_click=lambda j=job, c=jobs_container: _confirm_delete_job(j, c),
                ).props("flat dense color=negative").tooltip("Delete job")


def _toggle_job_enabled(job: Job, jobs_container: ui.column) -> None:
    updated = _job_service.toggle_enabled(job.id)
    if updated:
        state = "enabled" if updated.is_enabled else "disabled"
        ui.notification(f"Job '{updated.name}' {state}.", type="positive")
    _render_jobs_list(jobs_container)


def _run_job_now(job: Job, jobs_container: ui.column) -> None:
    notification = ui.notification(f"Triggering job '{job.name}'...", type="ongoing", timeout=None)
    try:
        flow_run = _job_service.run_job(job.id)
        notification.dismiss()
        run_path = prefect_client.run_ui_path(flow_run.id)
        ui.notification(
            f"Job '{job.name}' triggered. Run ID: {flow_run.name}",
            type="positive",
        )
        _open_prefect_iframe_dialog(f"Run — {job.name}", run_path)
    except Exception as exc:
        notification.dismiss()
        ui.notification(f"Could not trigger '{job.name}': {exc}", type="negative")
        _render_jobs_list(jobs_container)


def _confirm_delete_job(job: Job, jobs_container: ui.column) -> None:
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Delete job '{job.name}'?").classes("text-weight-bold")
        ui.label("This will also delete the Prefect deployment and all run history.").classes(
            "text-grey-7"
        )
        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            def _confirm_delete() -> None:
                _job_service.delete_job(job.id)
                dialog.close()
                if jobs_container:
                    _render_jobs_list(jobs_container)

            ui.button(
                "Delete",
                on_click=_confirm_delete,
            ).props("color=negative")
    dialog.open()


def _open_deployment_details(job: Job) -> None:
    if not job.prefect_deployment_id:
        ui.notification("No Prefect deployment registered for this job.", type="warning")
        return
    deployment_path = prefect_client.deployment_ui_path(UUID(job.prefect_deployment_id))
    _open_prefect_iframe_dialog(f"Deployment — {job.name}", deployment_path)


def _open_run_history(job: Job) -> None:
    runs = _job_service.list_executions(job.id)
    with ui.dialog() as dialog, ui.card().classes("w-full").style("min-width: 640px"):
        with ui.row().classes("w-full items-center justify-between q-mb-md"):
            ui.label(f"Run History — {job.name}").classes("text-h6")
            ui.button(icon="close", on_click=dialog.close).props("flat dense")

        if not runs:
            ui.label("No runs yet.").classes("text-grey-6")
        else:
            for run in runs:
                _render_flow_run_row(run, dialog)
    dialog.open()


def _render_flow_run_row(run: FlowRun, parent_dialog: ui.dialog) -> None:
    state_name = run.state_name or "UNKNOWN"
    color = _STATE_COLORS.get(state_name.upper(), "grey")
    started = str(run.start_time)[:19] if run.start_time else "—"
    duration = f"{int(run.total_run_time.total_seconds())}s" if run.total_run_time else "—"
    run_path = prefect_client.run_ui_path(run.id)

    def _open_run(r_path: str = run_path) -> None:
        parent_dialog.close()
        _open_prefect_iframe_dialog(f"Run — {run.name}", r_path)

    with ui.card().classes("w-full cursor-pointer hover:bg-grey-2").on("click", _open_run):
        with ui.row().classes("w-full items-center justify-between q-pa-sm"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("circle", color=color).classes("text-xs")
                ui.label(run.name or str(run.id)).classes("text-weight-medium")
                ui.label(state_name.upper()).classes(f"text-caption text-{color}")
            with ui.row().classes("items-center gap-4"):
                ui.label(started).classes("text-caption text-grey-6")
                ui.label(duration).classes("text-caption text-grey-6")


def _open_prefect_iframe_dialog(title: str, path: str) -> None:
    """Open a full-screen dialog embedding the Prefect UI at the given path."""
    prefect_url = f"{PREFECT_UI_BASE_PATH}/{path.lstrip('/')}"
    with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
        with ui.row().classes("w-full items-center justify-between q-pa-sm"):
            ui.label(title).classes("text-h6")
            with ui.row().classes("items-center gap-2"):
                ui.link("Open in new tab", prefect_url, new_tab=True).classes(
                    "text-caption text-primary"
                )
                ui.button(icon="close", on_click=dialog.close).props("flat dense")
        ui.html(
            f'<iframe src="{prefect_url}" '
            f'style="width:100%;height:calc(100vh - 80px);border:none;"></iframe>'
        )
    dialog.open()


def _open_job_dialog(job: Job | None, jobs_container: ui.column | None) -> None:
    is_edit = job is not None
    tasks: list[dict] = []
    task_elements: list[dict] = []

    if is_edit and job:
        tasks = [
            {
                "name": t.name,
                "executor_type": t.executor_type,
                "content": t.content,
                "file_path": t.file_path,
                "position": t.position,
            }
            for t in (job.tasks or [])
        ]

    with (
        ui.dialog() as dialog,
        ui.card().classes("w-full").style("min-width: 700px; max-height: 90vh; overflow-y: auto"),
    ):
        ui.label("Edit Job" if is_edit else "New Job").classes("text-h6 q-mb-md")

        name_input = ui.input("Job name", value=job.name if job else "").classes("w-full")
        desc_input = ui.textarea(
            "Description",
            value=job.description if job and job.description else "",
        ).classes("w-full")
        cron_input = ui.input(
            "Cron schedule (e.g. 0 0 * * *)",
            value=job.schedule_cron if job and job.schedule_cron else "",
        ).classes("w-full")

        ui.label("Tasks").classes("text-subtitle1 text-weight-bold q-mt-md")
        tasks_container = ui.column().classes("w-full gap-2")

        def render_tasks() -> None:
            task_elements.clear()
            tasks_container.clear()
            with tasks_container:
                for idx, task_def in enumerate(tasks):
                    els = _render_task_editor(task_def, idx, tasks, render_tasks)
                    task_elements.append(els)

        render_tasks()

        with ui.row().classes("q-mt-sm"):

            def _add_task() -> None:
                tasks.append(
                    {
                        "name": "New Task",
                        "executor_type": "sql",
                        "content": "",
                        "file_path": None,
                        "position": len(tasks),
                    }
                )
                render_tasks()

            ui.button("+ Add Task", on_click=_add_task).props("flat color=primary")

        with ui.row().classes("justify-end gap-2 q-mt-lg"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Save",
                on_click=lambda: _save_job(
                    job,
                    name_input.value,
                    desc_input.value,
                    cron_input.value,
                    tasks,
                    task_elements,
                    dialog,
                    jobs_container,
                ),
            ).props("color=primary")

    dialog.open()


def _render_task_editor(task_def: dict, idx: int, tasks: list[dict], on_change) -> dict:
    """Render a single task editor card and return a dict of element references."""
    elements: dict = {}

    with ui.card().classes("w-full bg-grey-1"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"Task {idx + 1}").classes("text-weight-bold")
            ui.button(
                icon="delete",
                on_click=lambda i=idx: [tasks.pop(i), on_change()],
            ).props("flat dense color=negative")

        elements["name"] = ui.input("Task name", value=task_def.get("name", "")).classes("w-full")

        initial_executor = task_def.get("executor_type", "sql")
        executor_select = ui.select(
            ["sql", "python"],
            label="Executor type",
            value=initial_executor,
        ).classes("w-full")
        elements["executor_type"] = executor_select

        use_file = bool(task_def.get("file_path"))
        mode_toggle = ui.toggle(
            ["Inline", "File"],
            value="File" if use_file else "Inline",
        ).classes("q-mt-sm")

        initial_lang = "SQL" if initial_executor == "sql" else "Python"
        inline_editor = (
            ui.codemirror(
                value=task_def.get("content", ""),
                language=initial_lang,  # type: ignore[arg-type]
                theme="githubLight",
            )
            .classes("w-full")
            .style("min-height: 120px")
        )

        workspace_files = _list_workspace_files(["sql", "py", "ipynb"])
        file_path = task_def.get("file_path")
        file_select = ui.select(
            workspace_files,
            label="Workspace file",
            value=file_path if file_path in workspace_files else None,
        ).classes("w-full")

        def _apply_mode(mode: str) -> None:
            if mode == "File":
                inline_editor.set_visibility(False)
                file_select.set_visibility(True)
            else:
                inline_editor.set_visibility(True)
                file_select.set_visibility(False)

        def _apply_executor_language(executor: str) -> None:
            lang = "SQL" if executor == "sql" else "Python"
            inline_editor.set_language(lang)  # type: ignore[arg-type]
            inline_editor.update()

        _apply_mode(mode_toggle.value)
        mode_toggle.on_value_change(lambda e: _apply_mode(e.value))
        executor_select.on_value_change(lambda e: _apply_executor_language(e.value))

        elements["content"] = inline_editor
        elements["file_path"] = file_select
        elements["mode"] = mode_toggle

    return elements


def _save_job(
    existing_job: Job | None,
    name: str,
    description: str,
    schedule_cron: str,
    tasks: list[dict],
    task_elements: list[dict],
    dialog,
    jobs_container: ui.column | None,
) -> None:
    if not name.strip():
        ui.notification("Job name is required.", type="warning")
        return

    _flush_task_elements_into_dicts(tasks, task_elements)

    cron = schedule_cron.strip() if schedule_cron.strip() else None

    if existing_job:
        saved_job = _job_service.update_job(
            existing_job.id,
            name=name,
            description=description or None,
            schedule_cron=cron,
        )
        if not saved_job:
            ui.notification("Failed to update job.", type="negative")
            return
        _job_service.replace_tasks(saved_job.id, tasks)
    else:
        saved_job = _job_service.create_job(name, description or None, cron)
        _job_service.replace_tasks(saved_job.id, tasks)

    dialog.close()
    ui.notification(f"Job '{saved_job.name}' saved.", type="positive")
    if jobs_container:
        _render_jobs_list(jobs_container)


def _flush_task_elements_into_dicts(tasks: list[dict], task_elements: list[dict]) -> None:
    """Read current UI element values into the task dicts before saving."""
    for idx, els in enumerate(task_elements):
        if idx >= len(tasks):
            break
        tasks[idx]["name"] = els["name"].value
        tasks[idx]["executor_type"] = els["executor_type"].value
        mode = els["mode"].value
        if mode == "File":
            tasks[idx]["file_path"] = els["file_path"].value
            tasks[idx]["content"] = ""
        else:
            tasks[idx]["content"] = els["content"].value
            tasks[idx]["file_path"] = None
