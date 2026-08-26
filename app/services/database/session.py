"""Session helpers and database initialization utilities."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.database.base import Base
from app.services.database.connection import DatabaseConnection


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager that yields a SQLAlchemy session and handles commit/rollback."""
    session = DatabaseConnection.session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> None:
    """Create all schemas and tables if they do not already exist."""
    engine = DatabaseConnection.engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS metastore"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS app"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    _apply_migrations(engine)
    DatabaseConnection.mark_available(True)


def _apply_migrations(engine) -> None:
    """Apply additive schema migrations for columns added after initial release."""
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE app.job_tasks ADD COLUMN IF NOT EXISTS file_path VARCHAR(1024) NULL")
        )
        conn.execute(
            text(
                "ALTER TABLE app.jobs"
                " ADD COLUMN IF NOT EXISTS prefect_deployment_id VARCHAR(36) NULL"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE app.jobs"
                " ADD COLUMN IF NOT EXISTS schedule_timezone VARCHAR(100)"
                " NOT NULL DEFAULT 'UTC'"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE app.jobs"
                " ADD COLUMN IF NOT EXISTS graph_version INTEGER NOT NULL DEFAULT 0"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS app.job_task_dependencies ("
                "  task_id INTEGER NOT NULL"
                "    REFERENCES app.job_tasks(id) ON DELETE CASCADE,"
                "  depends_on_task_id INTEGER NOT NULL"
                "    REFERENCES app.job_tasks(id) ON DELETE CASCADE,"
                "  PRIMARY KEY (task_id, depends_on_task_id),"
                "  CHECK (task_id <> depends_on_task_id)"
                ")"
            )
        )
        conn.execute(
            text(
                "INSERT INTO app.job_task_dependencies (task_id, depends_on_task_id) "
                "SELECT current_task.id, previous_task.id "
                "FROM app.jobs job "
                "JOIN app.job_tasks current_task ON current_task.job_id = job.id "
                "JOIN app.job_tasks previous_task "
                "  ON previous_task.job_id = current_task.job_id "
                " AND previous_task.position = current_task.position - 1 "
                "WHERE job.graph_version = 0 "
                "ON CONFLICT DO NOTHING"
            )
        )
        conn.execute(text("UPDATE app.jobs SET graph_version = 1 WHERE graph_version = 0"))
        conn.execute(text("ALTER TABLE app.jobs ALTER COLUMN graph_version SET DEFAULT 1"))
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS app.git_connections ("
                "  id SERIAL PRIMARY KEY,"
                "  name VARCHAR(255) NOT NULL,"
                "  provider_type VARCHAR(50) NOT NULL,"
                "  host VARCHAR(255),"
                "  token_encrypted BYTEA NOT NULL,"
                "  created_at TIMESTAMP DEFAULT now(),"
                "  updated_at TIMESTAMP DEFAULT now()"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS app.git_folders ("
                "  id SERIAL PRIMARY KEY,"
                "  workspace_path VARCHAR(1024) NOT NULL UNIQUE,"
                "  git_connection_id INTEGER NOT NULL"
                "    REFERENCES app.git_connections(id) ON DELETE CASCADE,"
                "  repo_url VARCHAR(1024) NOT NULL,"
                "  branch VARCHAR(255) NOT NULL DEFAULT 'main',"
                "  created_at TIMESTAMP DEFAULT now()"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS app.query_tabs ("
                "  id SERIAL PRIMARY KEY,"
                "  name VARCHAR(255) NOT NULL DEFAULT 'Query 1',"
                "  sql_content TEXT NOT NULL DEFAULT '',"
                "  position INTEGER NOT NULL DEFAULT 0,"
                "  created_at TIMESTAMP DEFAULT now(),"
                "  updated_at TIMESTAMP DEFAULT now()"
                ")"
            )
        )
        conn.commit()
