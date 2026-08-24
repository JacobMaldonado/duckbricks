"""Application startup orchestration."""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from app.config import WORKSPACE_PATH, validate_runtime_configuration
from app.services.database.session import init_database
from app.services.metastore import manager
from app.services.prefect import prefect_client

_log = logging.getLogger(__name__)


class MetastoreInitializer(Protocol):
    """Contract required to initialize the DuckLake metastore."""

    def initialize(self) -> dict:
        """Initialize the metastore and return its status."""


class PrefectInitializer(Protocol):
    """Contract required to initialize Prefect resources."""

    async def ensure_work_pool(self) -> None:
        """Ensure the configured work pool exists."""


class ApplicationStartup:
    """Initializes required runtime dependencies in a deterministic order."""

    def __init__(
        self,
        workspace_path: str = WORKSPACE_PATH,
        configuration_validator: Callable[[], None] = validate_runtime_configuration,
        database_initializer: Callable[[], None] = init_database,
        metastore_initializer: MetastoreInitializer = manager,
        prefect_initializer: PrefectInitializer = prefect_client,
        dependency_attempts: int = 3,
        retry_delay_seconds: float = 2.0,
    ) -> None:
        self._workspace_path = workspace_path
        self._configuration_validator = configuration_validator
        self._database_initializer = database_initializer
        self._metastore_initializer = metastore_initializer
        self._prefect_initializer = prefect_initializer
        self._dependency_attempts = dependency_attempts
        self._retry_delay_seconds = retry_delay_seconds

    async def run(self) -> None:
        """Validate configuration and initialize every required dependency."""
        self._configuration_validator()
        Path(self._workspace_path).mkdir(parents=True, exist_ok=True)

        for attempt in range(1, self._dependency_attempts + 1):
            try:
                await self._initialize_dependencies()
                return
            except Exception as exc:
                if attempt == self._dependency_attempts:
                    _log.error(
                        "Required dependency initialization failed after %d attempt(s) (%s).",
                        attempt,
                        type(exc).__name__,
                    )
                    raise RuntimeError("Required dependency initialization failed.") from None
                _log.warning(
                    "Required dependency initialization failed on attempt %d of %d (%s).",
                    attempt,
                    self._dependency_attempts,
                    type(exc).__name__,
                )
                await asyncio.sleep(self._retry_delay_seconds)

    async def _initialize_dependencies(self) -> None:
        """Initialize the database, metastore, and Prefect work pool once."""
        self._database_initializer()
        _log.info("Application database initialized.")

        self._metastore_initializer.initialize()
        _log.info("DuckLake metastore initialized.")

        await self._prefect_initializer.ensure_work_pool()
        _log.info("Prefect work pool initialized.")
