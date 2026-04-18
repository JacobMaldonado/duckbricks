"""Tests for JobService — skipped when PostgreSQL is not available."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_TESTS", "0") != "1",
    reason="Set INTEGRATION_TESTS=1 with a live PostgreSQL to run these tests",
)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.services.database.base import Base  # noqa: E402
from app.services.database.models.app import Job, JobTask  # noqa: E402
from app.services.jobs.job_service import JobService  # noqa: E402


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


class TestJobService:
    def test_create_and_list_jobs(self):
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
        service = JobService()
        job = service.create_job("Temp Job", None, None)
        assert service.delete_job(job.id) is True
        assert service.get_job(job.id) is None

    def test_update_job_changes_fields(self):
        service = JobService()
        job = service.create_job("Old Name", None, None)
        service.update_job(job.id, name="New Name")
        updated = service.get_job(job.id)
        assert updated.name == "New Name"
