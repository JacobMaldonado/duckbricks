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
        conn.commit()
