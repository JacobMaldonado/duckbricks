"""Jobs page — create, manage, and monitor scheduled DuckBricks jobs."""

from nicegui import ui

from app.services.database.models.app import Job
from app.services.jobs import JobService
from app.ui.components.layout import layout_frame

_job_service = JobService()


def _format_status_badge(status: str) -> str:
    color_map = {"success": "green", "failed": "red", "running": "blue", "cancelled": "grey"}
    color = color_map.get(status, "grey")
    return f'<span class="q-badge bg-{color} text-white q-pa-xs rounded">{status}</span>'


def jobs_page() -> None:
    """Render the Jobs management page."""
    layout_frame("Jobs")

    with ui.column().classes("w-full h-full p-4 gap-4"):
        _render_page_header()
        jobs_container = ui.column().classes("w-full gap-2")
        _render_jobs_list(jobs_container)


def _render_page_header() -> None:
    with ui.row().classes("w-full items-center justify-between"):
        ui.label("Jobs").classes("text-h5 text-weight-bold")
        ui.button("+ New Job", on_click=lambda: _open_job_dialog(None, None)).props("color=primary")


def _render_jobs_list(container: ui.column) -> None:
    container.clear()
    jobs = _job_service.list_jobs()

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
        _job_service.run_job(job.id)
        notification.dismiss()
        ui.notification(f"Job '{job.name}' completed successfully.", type="positive")
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
            columns = [
                {"name": "id", "label": "Run #", "field": "id", "align": "left"},
                {"name": "status", "label": "Status", "field": "status", "align": "left"},
                {
                    "name": "started_at",
                    "label": "Started",
                    "field": "started_at",
                    "align": "left",
                },
                {
                    "name": "duration_ms",
                    "label": "Duration (ms)",
                    "field": "duration_ms",
                    "align": "right",
                },
            ]
            rows = [
                {
                    "id": ex.id,
                    "status": ex.status,
                    "started_at": str(ex.started_at)[:19] if ex.started_at else "",
                    "duration_ms": ex.duration_ms or "",
                }
                for ex in executions
            ]
            ui.table(columns=columns, rows=rows).classes("w-full")
    dialog.open()


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
        task_name.on("blur", lambda e, t=task_def: t.update({"name": e.value}))

        executor_select = ui.select(
            ["sql", "python"],
            label="Executor type",
            value=task_def.get("executor_type", "sql"),
        ).classes("w-full")
        executor_select.on(
            "update:modelValue", lambda e, t=task_def: t.update({"executor_type": e.value})
        )

        content_area = ui.textarea(
            "Content (SQL query or Python script)",
            value=task_def.get("content", ""),
        ).classes("w-full font-mono")
        content_area.on("blur", lambda e, t=task_def: t.update({"content": e.value}))


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
