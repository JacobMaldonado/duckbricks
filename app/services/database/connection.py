"""SQLAlchemy engine and session factory for DuckBricks."""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages the SQLAlchemy engine and session factory lifecycle."""

    _engine = None
    _session_factory = None
    _available: bool = False

    @classmethod
    def initialize(cls) -> None:
        """Create the engine and session factory from DATABASE_URL."""
        safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
        logger.debug("Initializing database engine — target: %s", safe_url)
        cls._engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        cls._session_factory = sessionmaker(bind=cls._engine, autocommit=False, autoflush=False)
        logger.debug("Engine and session factory created successfully")

    @classmethod
    def is_available(cls) -> bool:
        """Return True if the database is reachable."""
        return cls._available

    @classmethod
    def mark_available(cls, available: bool) -> None:
        """Set the availability flag after a connectivity check."""
        cls._available = available

    @classmethod
    def check_connectivity(cls) -> bool:
        """Test the connection and update the availability flag. Returns True on success."""
        safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
        logger.debug("Checking database connectivity — target: %s", safe_url)
        try:
            with cls.engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            cls._available = True
            logger.info("Database connection established — %s", safe_url)
        except OperationalError as exc:
            cls._available = False
            logger.warning("Database connection failed — %s\n  Reason: %s", safe_url, exc.orig)
        return cls._available

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
