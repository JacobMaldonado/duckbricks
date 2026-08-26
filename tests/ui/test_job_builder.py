"""Contract tests for the Jobs dashboard and pipeline builder."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.services.jobs.models import JobRunSummary, JobTaskInput
from app.services.workspace import WorkspaceService
from app.ui.components.cron_schedule_builder import CronScheduleBuilder
from app.ui.components.job_flow_diagram import JobFlowDiagram
from app.ui.components.workspace_file_picker import (
    WORKSPACE_FILE_PICKER_CSS,
    WorkspaceFilePicker,
)
from app.ui.pages.job_editor import JOB_EDITOR_CSS, EditableJobTask
from app.ui.pages.jobs import JOBS_DASHBOARD_CSS, JobsDashboard


def test_mermaid_preview_contains_branch_and_join_edges() -> None:
    tasks = (
        JobTaskInput("extract", "Extract", "extract.py", "python"),
        JobTaskInput("left", "Left", "left.sql", "sql", ("extract",)),
        JobTaskInput("right", "Right", "right.sql", "sql", ("extract",)),
        JobTaskInput("load", "Load", "load.sql", "sql", ("left", "right")),
    )

    diagram = JobFlowDiagram.build_mermaid(tasks)

    assert "task_0 --> task_1" in diagram
    assert "task_0 --> task_2" in diagram
    assert "task_1 --> task_3" in diagram
    assert "task_2 --> task_3" in diagram


def test_mermaid_preview_escapes_user_labels() -> None:
    diagram = JobFlowDiagram.build_mermaid(
        (JobTaskInput("one", '<script>alert("x")</script>', "one.sql", "sql"),)
    )

    assert "<script>" not in diagram
    assert "&lt;script&gt;" in diagram


def test_job_editor_and_picker_are_responsive_full_height_workspaces() -> None:
    assert "grid-template-columns" in JOB_EDITOR_CSS
    assert "height: calc(100vh - 64px)" in JOB_EDITOR_CSS
    assert "workspace-picker-body" in WORKSPACE_FILE_PICKER_CSS
    assert "workspace-picker-preview" in WORKSPACE_FILE_PICKER_CSS


def test_editable_tasks_do_not_resave_legacy_inline_source() -> None:
    task = EditableJobTask(
        key="task-1",
        task_id=1,
        name="Legacy",
        legacy_content="print('legacy')",
    )

    assert task.to_input().legacy_content == ""
    assert task.to_input(include_legacy=True).legacy_content == "print('legacy')"


def test_dashboard_has_responsive_operations_layout() -> None:
    assert "jobs-kpis" in JOBS_DASHBOARD_CSS
    assert "jobs-table-header" in JOBS_DASHBOARD_CSS
    assert "@media (max-width: 720px)" in JOBS_DASHBOARD_CSS


def test_dashboard_calculates_a_labeled_seven_day_success_rate() -> None:
    now = datetime.now(UTC)
    runs = [
        JobRunSummary(
            run_id=uuid4(),
            deployment_id=None,
            name="success",
            state="COMPLETED",
            started_at=now - timedelta(days=1),
            ended_at=now,
            expected_start_time=now,
            duration_seconds=1,
            run_count=1,
        ),
        JobRunSummary(
            run_id=uuid4(),
            deployment_id=None,
            name="failed",
            state="FAILED",
            started_at=now - timedelta(days=2),
            ended_at=now,
            expected_start_time=now,
            duration_seconds=1,
            run_count=1,
        ),
    ]

    assert JobsDashboard._success_rate(runs) == "50%"


def test_cron_builder_classifies_supported_presets() -> None:
    assert CronScheduleBuilder._mode_for_cron(None) == "Manual"
    assert CronScheduleBuilder._mode_for_cron("15 * * * *") == "Hourly"
    assert CronScheduleBuilder._mode_for_cron("30 6 * * *") == "Daily"
    assert CronScheduleBuilder._mode_for_cron("broken") == "Custom"


def test_workspace_picker_filters_to_executable_files(tmp_path) -> None:
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "valid.sql").write_text("SELECT 1", encoding="utf-8")
    (tmp_path / "models" / "notes.md").write_text("notes", encoding="utf-8")
    workspace_service = WorkspaceService(str(tmp_path))
    picker = WorkspaceFilePicker(workspace_service, lambda _: None)

    filtered = picker._filter_nodes(workspace_service.list_tree(), "valid")

    assert len(filtered) == 1
    assert [node.name for node in filtered[0].children] == ["valid.sql"]
