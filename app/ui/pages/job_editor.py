"""Dedicated create/edit experience for workspace-backed job DAGs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from nicegui import ui

from app.config import WORKSPACE_PATH
from app.services.database.models.app import Job
from app.services.jobs import JobService
from app.services.jobs.graph_service import JobGraphService
from app.services.jobs.models import JobDefinitionInput, JobTaskInput
from app.services.jobs.schedule_service import JobScheduleService
from app.services.workspace import WorkspaceService
from app.ui.components.cron_schedule_builder import CronScheduleBuilder
from app.ui.components.job_flow_diagram import JobFlowDiagram
from app.ui.components.layout import layout_frame
from app.ui.components.workspace_file_picker import WorkspaceFilePicker

JOB_EDITOR_CSS = """
<style>
.job-editor-page { height: calc(100vh - 64px); overflow: hidden; background: #fafafa; }
.job-editor-shell {
    display: grid;
    grid-template-columns: minmax(520px, 1.15fr) minmax(360px, .85fr);
    flex: 1;
    min-height: 0;
}
.job-editor-form { min-height: 0; overflow-y: auto; }
.job-editor-preview { min-height: 0; overflow-y: auto; border-left: 1px solid #e0e0e0; }
.job-task-card { border: 1px solid #e0e0e0; box-shadow: none; }
.job-editor-preview .mermaid { display: flex; justify-content: center; }
@media (max-width: 1000px) {
    .job-editor-page { height: auto; min-height: calc(100vh - 64px); overflow: auto; }
    .job-editor-shell { display: flex; flex-direction: column; }
    .job-editor-form, .job-editor-preview { overflow: visible; }
    .job-editor-preview { border-left: 0; border-top: 1px solid #e0e0e0; min-height: 420px; }
}
</style>
"""


@dataclass(slots=True)
class EditableJobTask:
    """Mutable task state owned by one job-editor client."""

    key: str
    name: str
    file_path: str | None = None
    executor_type: str = "sql"
    depends_on: list[str] = field(default_factory=list)
    task_id: int | None = None
    legacy_content: str = ""

    def to_input(self, *, include_legacy: bool = False) -> JobTaskInput:
        return JobTaskInput(
            key=self.key,
            name=self.name,
            file_path=self.file_path,
            executor_type=self.executor_type,
            depends_on=tuple(self.depends_on),
            task_id=self.task_id,
            legacy_content=self.legacy_content if include_legacy else "",
        )


class JobEditorPage:
    """Coordinates a workspace-only job form and its live DAG preview."""

    def __init__(self, job_service: JobService, workspace_service: WorkspaceService) -> None:
        self._job_service = job_service
        self._workspace_service = workspace_service
        self._job: Job | None = None
        self._tasks: list[EditableJobTask] = []
        self._tasks_container: ui.column | None = None
        self._diagram_container: ui.column | None = None
        self._name_input: ui.input | None = None
        self._description_input: ui.textarea | None = None
        self._schedule_builder: CronScheduleBuilder | None = None

    def render(self, job_id: int | None = None) -> None:
        layout_frame("Jobs")
        ui.add_head_html(JOB_EDITOR_CSS)
        if job_id is not None:
            self._job = self._job_service.get_job(job_id)
            if not self._job:
                self._render_missing_job(job_id)
                return
            self._tasks = self._editable_tasks(self._job)
        if not self._tasks:
            self._tasks.append(self._new_task())

        with ui.column().classes("w-full gap-0 job-editor-page"):
            self._render_header()
            with ui.element("div").classes("w-full job-editor-shell"):
                self._render_form()
                self._render_preview()

    def _render_header(self) -> None:
        with ui.row().classes("w-full items-center gap-3 q-px-lg q-py-md bg-white border-b"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/jobs")).props(
                "flat round color=grey-7 aria-label=Back"
            )
            with ui.column().classes("gap-0"):
                ui.label("Edit job" if self._job else "New job").classes(
                    "text-h5 text-weight-medium"
                )
                ui.label(
                    "Build a workspace-backed pipeline and preview its execution graph."
                ).classes("text-caption text-grey-6")
            ui.space()
            ui.badge("DRAFT", color="grey-6").props("outline")
            ui.button("Validate", icon="rule", on_click=self._validate).props("flat color=primary")
            ui.button("Save job", icon="save", on_click=self._save).props("color=primary")

    def _render_form(self) -> None:
        with ui.column().classes("job-editor-form w-full q-pa-lg gap-4"):
            with ui.card().classes("w-full q-pa-md gap-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("edit_note", color="primary")
                    ui.label("Details").classes("text-subtitle1 text-weight-medium")
                self._name_input = (
                    ui.input("Job name", value=self._job.name if self._job else "")
                    .props("outlined")
                    .classes("w-full")
                )
                self._description_input = (
                    ui.textarea(
                        "Description",
                        value=self._job.description if self._job and self._job.description else "",
                    )
                    .props("outlined autogrow")
                    .classes("w-full")
                )

            self._schedule_builder = CronScheduleBuilder(
                self._job.schedule_cron if self._job else None,
                self._job.schedule_timezone if self._job else "UTC",
                is_enabled=self._job.is_enabled if self._job else True,
            )
            self._schedule_builder.render()

            with ui.row().classes("w-full items-end"):
                with ui.column().classes("gap-0"):
                    ui.label("Tasks").classes("text-h6 text-weight-medium")
                    ui.label(
                        "Tasks without dependencies start together; downstream tasks wait for all "
                        "selected inputs."
                    ).classes("text-caption text-grey-6")
                ui.space()
                ui.button("Add task", icon="add", on_click=self._add_task).props(
                    "outline color=primary"
                )
            self._tasks_container = ui.column().classes("w-full gap-3")
            self._render_tasks()

    def _render_preview(self) -> None:
        with ui.column().classes("job-editor-preview w-full bg-white gap-0"):
            with ui.column().classes("w-full gap-0 q-pa-md border-b"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("account_tree", color="primary")
                    ui.label("Flow preview").classes("text-subtitle1 text-weight-medium")
                ui.label("This is the dependency graph Prefect will execute.").classes(
                    "text-caption text-grey-6"
                )
            self._diagram_container = ui.column().classes("w-full q-pa-lg")
            self._render_diagram()

    def _render_tasks(self) -> None:
        if not self._tasks_container:
            return
        self._tasks_container.clear()
        with self._tasks_container:
            for index, task in enumerate(self._tasks):
                self._render_task(task, index)

    def _render_task(self, task: EditableJobTask, index: int) -> None:
        with ui.card().classes("w-full q-pa-md gap-3 job-task-card"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.badge(str(index + 1), color="primary")
                ui.label(task.name or "Unnamed task").classes("text-subtitle2 text-weight-medium")
                if task.file_path:
                    ui.badge(task.executor_type.upper(), color="blue-grey").props("outline")
                elif task.legacy_content:
                    ui.badge("LEGACY INLINE", color="orange").props("outline")
                ui.space()
                ui.button(
                    icon="arrow_upward", on_click=lambda t=task: self._move_task(t, -1)
                ).props(f"flat round dense color=grey-7{' disable' if index == 0 else ''}").tooltip(
                    "Move up"
                )
                ui.button(
                    icon="arrow_downward", on_click=lambda t=task: self._move_task(t, 1)
                ).props(
                    "flat round dense color=grey-7"
                    + (" disable" if index == len(self._tasks) - 1 else "")
                ).tooltip("Move down")
                ui.button(icon="delete", on_click=lambda t=task: self._remove_task(t)).props(
                    "flat round dense color=negative aria-label=Delete"
                ).tooltip("Delete task")

            name_input = (
                ui.input("Task name", value=task.name).props("outlined dense").classes("w-full")
            )

            def rename(event, current_task: EditableJobTask = task) -> None:
                current_task.name = event.value or ""
                self._render_diagram()

            name_input.on_value_change(rename)

            with ui.row().classes("w-full items-center gap-3 q-pa-sm bg-grey-1 rounded"):
                icon = "description" if task.executor_type == "sql" else "code"
                color = "blue-7" if task.executor_type == "sql" else "green-7"
                ui.icon(icon, color=color, size="24px")
                with ui.column().classes("gap-0 min-w-0 col"):
                    source_name = (
                        Path(task.file_path).name if task.file_path else "No file selected"
                    )
                    ui.label(source_name).classes("text-body2 text-weight-medium ellipsis")
                    ui.label(task.file_path or "Choose a .sql or .py workspace file").classes(
                        "text-caption text-grey-6 ellipsis"
                    )
                ui.button(
                    "Replace" if task.file_path else "Choose file",
                    icon="folder_open",
                    on_click=lambda t=task: self._choose_file(t),
                ).props("outline dense color=primary")

            if task.legacy_content and not task.file_path:
                with ui.row().classes("w-full items-center gap-2 q-pa-sm bg-orange-1 rounded"):
                    ui.icon("warning", color="orange-8")
                    ui.label(
                        "Legacy inline source: choose a workspace file before this job can be "
                        "saved."
                    ).classes("text-caption text-orange-9")

            dependency_options = {
                candidate.key: candidate.name or f"Task {candidate_index + 1}"
                for candidate_index, candidate in enumerate(self._tasks)
                if candidate.key != task.key
            }
            dependency_select = (
                ui.select(
                    dependency_options,
                    value=[key for key in task.depends_on if key in dependency_options],
                    label="Depends on",
                )
                .props("outlined dense multiple use-chips clearable")
                .classes("w-full")
            )

            def update_dependencies(event, current_task: EditableJobTask = task) -> None:
                current_task.depends_on = list(event.value or [])
                self._render_diagram()

            dependency_select.on_value_change(update_dependencies)

    def _render_diagram(self) -> None:
        if not self._diagram_container:
            return
        self._diagram_container.clear()
        with self._diagram_container:
            try:
                inputs = tuple(task.to_input(include_legacy=True) for task in self._tasks)
                JobGraphService.validate_inputs(inputs)
                JobFlowDiagram.render(inputs)
            except ValueError as exc:
                with ui.column().classes("w-full items-center q-pa-lg gap-2"):
                    ui.icon("error_outline", color="negative", size="36px")
                    ui.label(str(exc)).classes("text-body2 text-negative text-center")

    def _add_task(self) -> None:
        dependencies = [self._tasks[-1].key] if self._tasks else []
        self._tasks.append(self._new_task(depends_on=dependencies))
        self._render_tasks()
        self._render_diagram()

    def _remove_task(self, task: EditableJobTask) -> None:
        if len(self._tasks) == 1:
            ui.notification("A job requires at least one task.", type="warning")
            return
        self._tasks.remove(task)
        for candidate in self._tasks:
            candidate.depends_on = [key for key in candidate.depends_on if key != task.key]
        self._render_tasks()
        self._render_diagram()

    def _move_task(self, task: EditableJobTask, offset: int) -> None:
        index = self._tasks.index(task)
        target = index + offset
        if target < 0 or target >= len(self._tasks):
            return
        self._tasks[index], self._tasks[target] = self._tasks[target], self._tasks[index]
        self._render_tasks()
        self._render_diagram()

    def _choose_file(self, task: EditableJobTask) -> None:
        def select_file(relative_path: str) -> None:
            task.file_path = relative_path
            task.executor_type = JobGraphService.executor_for_path(relative_path)
            task.legacy_content = ""
            if not task.name.strip() or task.name.startswith("New task"):
                task.name = Path(relative_path).stem.replace("_", " ").title()
            self._render_tasks()
            self._render_diagram()

        WorkspaceFilePicker(
            self._workspace_service,
            select_file,
            selected_path=task.file_path,
        ).open()

    def _definition(self) -> JobDefinitionInput:
        if not self._name_input or not self._description_input or not self._schedule_builder:
            raise RuntimeError("The job editor is not ready.")
        return JobDefinitionInput(
            name=str(self._name_input.value or ""),
            description=str(self._description_input.value or "") or None,
            schedule_cron=self._schedule_builder.cron_expression,
            schedule_timezone=self._schedule_builder.timezone,
            is_enabled=self._schedule_builder.is_enabled,
            tasks=tuple(task.to_input() for task in self._tasks),
        )

    def _validate(self) -> None:
        try:
            definition = self._definition()
            if not definition.name.strip():
                raise ValueError("Job name is required.")
            JobScheduleService.validate(definition.schedule_cron, definition.schedule_timezone)
            JobGraphService.validate_inputs(definition.tasks)
            for task in definition.tasks:
                if task.file_path:
                    path = Path(self._workspace_service.absolute_path(task.file_path))
                    if not path.is_file():
                        raise ValueError(f"Workspace file does not exist: {task.file_path}.")
            ui.notification("Job definition is valid.", type="positive")
        except ValueError as exc:
            ui.notification(str(exc), type="negative")

    def _save(self) -> None:
        try:
            saved_job = self._job_service.save_job_definition(
                self._definition(),
                job_id=self._job.id if self._job else None,
            )
        except Exception as exc:
            ui.notification(f"Could not save job: {exc}", type="negative")
            return
        ui.notification(f"Job '{saved_job.name}' saved.", type="positive")
        ui.navigate.to(f"/jobs/{saved_job.id}")

    @staticmethod
    def _new_task(depends_on: list[str] | None = None) -> EditableJobTask:
        return EditableJobTask(
            key=f"draft-{uuid4()}",
            name="New task",
            depends_on=list(depends_on or []),
        )

    @staticmethod
    def _editable_tasks(job: Job) -> list[EditableJobTask]:
        key_by_task_id = {task.id: f"task-{task.id}" for task in job.tasks}
        return [
            EditableJobTask(
                key=key_by_task_id[task.id],
                task_id=task.id,
                name=task.name,
                file_path=task.file_path,
                executor_type=task.executor_type,
                depends_on=[
                    key_by_task_id[edge.depends_on_task_id]
                    for edge in task.dependency_edges
                    if edge.depends_on_task_id in key_by_task_id
                ],
                legacy_content=task.content,
            )
            for task in sorted(job.tasks, key=lambda item: item.position)
        ]

    @staticmethod
    def _render_missing_job(job_id: int) -> None:
        with ui.column().classes("w-full items-center justify-center q-pa-xl gap-3"):
            ui.icon("error_outline", color="negative", size="44px")
            ui.label(f"Job {job_id} was not found.").classes("text-h6")
            ui.button("Back to jobs", on_click=lambda: ui.navigate.to("/jobs")).props(
                "color=primary"
            )


def job_editor_page(job_id: int | None = None) -> None:
    """Render the create or edit route."""
    JobEditorPage(JobService(), WorkspaceService(WORKSPACE_PATH)).render(job_id)
