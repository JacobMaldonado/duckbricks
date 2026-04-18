"""SQLAlchemy engine and session factory for DuckBricks."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL


class DatabaseConnection:
    """Manages the SQLAlchemy engine and session factory lifecycle."""

    _engine = None
    _session_factory = None

    @classmethod
    def initialize(cls) -> None:
        """Create the engine and session factory from DATABASE_URL."""
        cls._engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        cls._session_factory = sessionmaker(bind=cls._engine, autocommit=False, autoflush=False)

    @classmethod
    def engine(cls):
        """Return the SQLAlchemy engine, initializing if needed."""
        if cls._engine is None:
            cls.initialize()
        return cls._engine

    @classmethod
    def session(cls) -> Session:
        """Open and return a new SQLAlchemy session."""
        if cls._session_factory is None:
            cls.initialize()
        return cls._session_factory()
