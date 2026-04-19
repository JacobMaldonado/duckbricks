"""Jobs page — create, manage, and monitor scheduled DuckBricks jobs."""

from pathlib import Path

from nicegui import ui
from sqlalchemy.exc import OperationalError

from app.config import WORKSPACE_PATH
from app.services.database.connection import DatabaseConnection
from app.services.database.models.app import Job
from app.services.jobs import JobService
from app.ui.components.layout import layout_frame

_job_service = JobService()


def _format_status_badge(status: str) -> str:
    color_map = {"success": "green", "failed": "red", "running": "blue", "cancelled": "grey"}
    color = color_map.get(status, "grey")
    return f'<span class="q-badge bg-{color} text-white q-pa-xs rounded">{status}</span>'


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
                ui.icon(status_icon).classes(f"text-{status_color}")

                ui.button(
                    icon="play_arrow",
                    on_click=lambda j=job, c=jobs_container: _run_job_now(j, c),
                ).props("flat dense color=primary").tooltip("Run now")
                ui.button(icon="history", on_click=lambda j=job: _open_run_history(j)).props(
                    "flat dense color=grey"
                ).tooltip("View run history")
                ui.button(
                    icon="edit",
                    on_click=lambda j=job, c=jobs_container: _open_job_dialog(j, c),
                ).props("flat dense color=grey").tooltip("Edit job")
                ui.button(
                    icon="delete",
                    on_click=lambda j=job, c=jobs_container: _confirm_delete_job(j, c),
                ).props("flat dense color=negative").tooltip("Delete job")


def _run_job_now(job: Job, jobs_container: ui.column) -> None:
    notification = ui.notification(f"Running job '{job.name}'...", type="ongoing", timeout=None)
    try:
        execution = _job_service.run_job(job.id)
        notification.dismiss()
        ui.navigate.to(f"/jobs/execution/{execution.id}")
    except Exception as e:
        notification.dismiss()
        ui.notification(f"Job '{job.name}' failed: {e}", type="negative")
        _render_jobs_list(jobs_container)


def _confirm_delete_job(job: Job, jobs_container: ui.column) -> None:
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Delete job '{job.name}'?").classes("text-weight-bold")
        ui.label("This will also delete all run history.").classes("text-grey-7")
        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Delete",
                on_click=lambda: [
                    _job_service.delete_job(job.id),
                    dialog.close(),
                    _render_jobs_list(jobs_container),
                ],
            ).props("color=negative")
    dialog.open()


def _open_run_history(job: Job) -> None:
    executions = _job_service.list_executions(job.id)
    with ui.dialog() as dialog, ui.card().classes("w-full").style("min-width: 600px"):
        with ui.row().classes("w-full items-center justify-between q-mb-md"):
            ui.label(f"Run History — {job.name}").classes("text-h6")
            ui.button(icon="close", on_click=dialog.close).props("flat dense")

        if not executions:
            ui.label("No runs yet.").classes("text-grey-6")
        else:
            for ex in executions:
                _render_execution_summary_row(ex, dialog)
    dialog.open()


def _render_execution_summary_row(execution, dialog) -> None:
    status_colors = {
        "success": "green",
        "failed": "red",
        "running": "blue",
        "cancelled": "grey",
    }
    color = status_colors.get(execution.status, "grey")
    started = str(execution.started_at)[:19] if execution.started_at else "—"
    duration = f"{execution.duration_ms} ms" if execution.duration_ms else "—"

    with (
        ui.card()
        .classes("w-full cursor-pointer hover:bg-grey-2")
        .on(
            "click",
            lambda ex=execution: [dialog.close(), ui.navigate.to(f"/jobs/execution/{ex.id}")],
        )
    ):
        with ui.row().classes("w-full items-center justify-between q-pa-sm"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("circle", color=color).classes("text-xs")
                ui.label(f"Run #{execution.id}").classes("text-weight-medium")
                ui.label(execution.status.upper()).classes(f"text-caption text-{color}")
            with ui.row().classes("items-center gap-4"):
                ui.label(started).classes("text-caption text-grey-6")
                ui.label(duration).classes("text-caption text-grey-6")


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
            ui.button(
                "+ Add Task",
                on_click=lambda: [
                    tasks.append(
                        {
                            "name": "New Task",
                            "executor_type": "sql",
                            "content": "",
                            "file_path": None,
                            "position": len(tasks),
                        }
                    ),
                    render_tasks(),
                ],
            ).props("flat color=primary")

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

        elements["executor_type"] = ui.select(
            ["sql", "python"],
            label="Executor type",
            value=task_def.get("executor_type", "sql"),
        ).classes("w-full")

        use_file = bool(task_def.get("file_path"))
        mode_toggle = ui.toggle(
            ["Inline", "File"],
            value="File" if use_file else "Inline",
        ).classes("q-mt-sm")

        inline_area = ui.textarea(
            "Content (SQL query or Python script)",
            value=task_def.get("content", ""),
        ).classes("w-full font-mono")

        workspace_files = _list_workspace_files(["sql", "py", "ipynb"])
        file_path = task_def.get("file_path")
        file_select = ui.select(
            workspace_files,
            label="Workspace file",
            value=file_path if file_path in workspace_files else None,
        ).classes("w-full")

        def _apply_mode(mode: str) -> None:
            if mode == "File":
                inline_area.set_visibility(False)
                file_select.set_visibility(True)
            else:
                inline_area.set_visibility(True)
                file_select.set_visibility(False)

        _apply_mode(mode_toggle.value)
        mode_toggle.on_value_change(lambda e: _apply_mode(e.value))

        elements["content"] = inline_area
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
        job = _job_service.update_job(
            existing_job.id,
            name=name,
            description=description or None,
            schedule_cron=cron,
        )
        _job_service.replace_tasks(job.id, tasks)
    else:
        job = _job_service.create_job(name, description or None, cron)
        _job_service.replace_tasks(job.id, tasks)

    dialog.close()
    ui.notification(f"Job '{job.name}' saved.", type="positive")
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
                ui.icon(status_icon).classes(f"text-{status_color}")

                ui.button(
                    icon="play_arrow",
                    on_click=lambda j=job, c=jobs_container: _run_job_now(j, c),
                ).props("flat dense color=primary").tooltip("Run now")
                ui.button(icon="history", on_click=lambda j=job: _open_run_history(j)).props(
                    "flat dense color=grey"
                ).tooltip("View run history")
                ui.button(
                    icon="edit",
                    on_click=lambda j=job, c=jobs_container: _open_job_dialog(j, c),
                ).props("flat dense color=grey").tooltip("Edit job")
                ui.button(
                    icon="delete",
                    on_click=lambda j=job, c=jobs_container: _confirm_delete_job(j, c),
                ).props("flat dense color=negative").tooltip("Delete job")


def _run_job_now(job: Job, jobs_container: ui.column) -> None:
    notification = ui.notification(f"Running job '{job.name}'...", type="ongoing", timeout=None)
    try:
        execution = _job_service.run_job(job.id)
        notification.dismiss()
        ui.navigate.to(f"/jobs/execution/{execution.id}")
    except Exception as e:
        notification.dismiss()
        ui.notification(f"Job '{job.name}' failed: {e}", type="negative")
        _render_jobs_list(jobs_container)


def _confirm_delete_job(job: Job, jobs_container: ui.column) -> None:
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Delete job '{job.name}'?").classes("text-weight-bold")
        ui.label("This will also delete all run history.").classes("text-grey-7")
        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Delete",
                on_click=lambda: [
                    _job_service.delete_job(job.id),
                    dialog.close(),
                    _render_jobs_list(jobs_container),
                ],
            ).props("color=negative")
    dialog.open()


def _open_run_history(job: Job) -> None:
    executions = _job_service.list_executions(job.id)
    with ui.dialog() as dialog, ui.card().classes("w-full").style("min-width: 600px"):
        with ui.row().classes("w-full items-center justify-between q-mb-md"):
            ui.label(f"Run History — {job.name}").classes("text-h6")
            ui.button(icon="close", on_click=dialog.close).props("flat dense")

        if not executions:
            ui.label("No runs yet.").classes("text-grey-6")
        else:
            for ex in executions:
                _render_execution_summary_row(ex, dialog)
    dialog.open()


def _render_execution_summary_row(execution, dialog) -> None:
    status_colors = {
        "success": "green",
        "failed": "red",
        "running": "blue",
        "cancelled": "grey",
    }
    color = status_colors.get(execution.status, "grey")
    started = str(execution.started_at)[:19] if execution.started_at else "—"
    duration = f"{execution.duration_ms} ms" if execution.duration_ms else "—"

    with (
        ui.card()
        .classes("w-full cursor-pointer hover:bg-grey-2")
        .on(
            "click",
            lambda ex=execution: [dialog.close(), ui.navigate.to(f"/jobs/execution/{ex.id}")],
        )
    ):
        with ui.row().classes("w-full items-center justify-between q-pa-sm"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("circle", color=color).classes("text-xs")
                ui.label(f"Run #{execution.id}").classes("text-weight-medium")
                ui.label(execution.status.upper()).classes(f"text-caption text-{color}")
            with ui.row().classes("items-center gap-4"):
                ui.label(started).classes("text-caption text-grey-6")
                ui.label(duration).classes("text-caption text-grey-6")


def _open_job_dialog(job: Job | None, jobs_container: ui.column | None) -> None:
    is_edit = job is not None
    tasks: list[dict] = []

    if is_edit and job:
        tasks = [
            {
                "name": t.name,
                "executor_type": t.executor_type,
                "content": t.content,
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

        def render_tasks():
            tasks_container.clear()
            with tasks_container:
                for idx, task_def in enumerate(tasks):
                    _render_task_editor(task_def, idx, tasks, render_tasks)

        render_tasks()

        with ui.row().classes("q-mt-sm"):
            ui.button(
                "+ Add Task",
                on_click=lambda: [
                    tasks.append(
                        {
                            "name": "New Task",
                            "executor_type": "sql",
                            "content": "",
                            "position": len(tasks),
                        }
                    ),
                    render_tasks(),
                ],
            ).props("flat color=primary")

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
                    dialog,
                    jobs_container,
                ),
            ).props("color=primary")

    dialog.open()


def _render_task_editor(task_def: dict, idx: int, tasks: list[dict], on_change) -> None:
    with ui.card().classes("w-full bg-grey-1"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"Task {idx + 1}").classes("text-weight-bold")
            ui.button(
                icon="delete",
                on_click=lambda i=idx: [tasks.pop(i), on_change()],
            ).props("flat dense color=negative")

        task_name = ui.input("Task name", value=task_def.get("name", "")).classes("w-full")
        task_name.on("blur", lambda _e, el=task_name, t=task_def: t.update({"name": el.value}))

        ui.select(
            ["sql", "python"],
            label="Executor type",
            value=task_def.get("executor_type", "sql"),
            on_change=lambda e, t=task_def: t.update({"executor_type": e.value}),
        ).classes("w-full")

        content_area = ui.textarea(
            "Content (SQL query or Python script)",
            value=task_def.get("content", ""),
        ).classes("w-full font-mono")
        content_area.on(
            "blur", lambda _e, el=content_area, t=task_def: t.update({"content": el.value})
        )


def _save_job(
    existing_job: Job | None,
    name: str,
    description: str,
    schedule_cron: str,
    tasks: list[dict],
    dialog,
    jobs_container: ui.column | None,
) -> None:
    if not name.strip():
        ui.notification("Job name is required.", type="warning")
        return

    cron = schedule_cron.strip() if schedule_cron.strip() else None

    if existing_job:
        job = _job_service.update_job(
            existing_job.id,
            name=name,
            description=description or None,
            schedule_cron=cron,
        )
    else:
        job = _job_service.create_job(name, description or None, cron)

    for idx, task_def in enumerate(tasks):
        _job_service.add_task(
            job_id=job.id,
            name=task_def.get("name", f"Task {idx + 1}"),
            executor_type=task_def.get("executor_type", "sql"),
            content=task_def.get("content", ""),
            position=idx,
        )

    dialog.close()
    ui.notification(f"Job '{job.name}' saved.", type="positive")
    if jobs_container:
        _render_jobs_list(jobs_container)
