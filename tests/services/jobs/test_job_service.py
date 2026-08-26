"""Tests for JobService — skipped when PostgreSQL is not available."""

import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_TESTS", "0") != "1",
    reason="Set INTEGRATION_TESTS=1 with a live PostgreSQL to run these tests",
)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.services.database.base import Base  # noqa: E402
from app.services.jobs.job_service import JobService  # noqa: E402
from app.services.jobs.models import JobDefinitionInput, JobTaskInput  # noqa: E402


@pytest.fixture(autouse=True)
def pg_db(monkeypatch):
    """Use the real PostgreSQL engine but run each test in an isolated schema."""
    import app.services.database.connection as conn_module

    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    monkeypatch.setattr(conn_module.DatabaseConnection, "_engine", engine)
    monkeypatch.setattr(conn_module.DatabaseConnection, "_session_factory", factory)
    yield
    Base.metadata.drop_all(bind=engine)


def _mock_prefect():
    """Return a context manager that stubs out all Prefect API calls in JobService."""
    fake_deployment_id = uuid4()
    fake_run = MagicMock()
    fake_run.id = uuid4()
    fake_run.name = "mock-run"

    def run(coroutine):
        operation = coroutine.cr_code.co_name
        coroutine.close()
        if operation == "create_deployment":
            return fake_deployment_id
        if operation == "trigger_run":
            return fake_run
        if operation == "list_runs":
            return [fake_run]
        return None

    return patch("app.services.jobs.job_service._run_prefect", side_effect=run)


class TestJobService:
    def test_create_and_list_jobs(self):
        with _mock_prefect():
            service = JobService()
            service.create_job("My Job", "A test job", "0 0 * * *")
            jobs = service.list_jobs()
        assert len(jobs) >= 1
        assert any(j.name == "My Job" for j in jobs)

    def test_get_job_returns_none_for_missing_id(self):
        service = JobService()
        result = service.get_job(9999)
        assert result is None

    def test_delete_job_removes_it(self):
        with _mock_prefect():
            service = JobService()
            job = service.create_job("Temp Job", None, None)
            assert service.delete_job(job.id) is True
            assert service.get_job(job.id) is None

    def test_update_job_changes_fields(self):
        with _mock_prefect():
            service = JobService()
            job = service.create_job("Old Name", None, None)
            service.update_job(job.id, name="New Name")
            updated = service.get_job(job.id)
        assert updated.name == "New Name"

    def test_saves_branched_dependencies_and_preserves_task_ids(self, tmp_path, monkeypatch):
        import app.services.jobs.job_service as job_service_module

        (tmp_path / "extract.py").write_text("print('extract')", encoding="utf-8")
        (tmp_path / "left.sql").write_text("SELECT 1", encoding="utf-8")
        (tmp_path / "right.sql").write_text("SELECT 2", encoding="utf-8")
        monkeypatch.setattr(job_service_module, "WORKSPACE_PATH", str(tmp_path))
        service = JobService()
        definition = JobDefinitionInput(
            name="Branched",
            description=None,
            schedule_cron="0 6 * * *",
            schedule_timezone="America/Mexico_City",
            tasks=(
                JobTaskInput("extract", "Extract", "extract.py", "python"),
                JobTaskInput("left", "Left", "left.sql", "sql", ("extract",)),
                JobTaskInput("right", "Right", "right.sql", "sql", ("extract",)),
            ),
        )

        with patch.object(service, "_register_deployment"):
            saved = service.save_job_definition(definition)

        ids_by_name = {task.name: task.id for task in saved.tasks}
        left = next(task for task in saved.tasks if task.name == "Left")
        right = next(task for task in saved.tasks if task.name == "Right")
        assert [edge.depends_on_task_id for edge in left.dependency_edges] == [
            ids_by_name["Extract"]
        ]
        assert [edge.depends_on_task_id for edge in right.dependency_edges] == [
            ids_by_name["Extract"]
        ]

        updated_definition = JobDefinitionInput(
            name="Branched updated",
            description=None,
            schedule_cron=None,
            tasks=tuple(
                JobTaskInput(
                    key=task.name.casefold(),
                    task_id=task.id,
                    name=task.name,
                    file_path=task.file_path,
                    executor_type=task.executor_type,
                    depends_on=("extract",) if task.name in {"Left", "Right"} else (),
                )
                for task in saved.tasks
            ),
        )
        with patch.object(service, "_sync_deployment"):
            updated = service.save_job_definition(updated_definition, job_id=saved.id)

        assert {task.name: task.id for task in updated.tasks} == ids_by_name
