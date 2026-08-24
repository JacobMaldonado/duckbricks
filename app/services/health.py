"""Runtime dependency health checks."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.config import MARIMO_INTERNAL_URL, PREFECT_INTERNAL_URL
from app.services.database.connection import DatabaseConnection
from app.services.metastore import manager

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HealthReport:
    """Sanitized readiness state for DuckBricks runtime dependencies."""

    checks: dict[str, str]

    @property
    def is_ready(self) -> bool:
        """Return True when every required dependency is available."""
        return all(status == "up" for status in self.checks.values())

    def as_dict(self) -> dict[str, object]:
        """Return the public health response without dependency error details."""
        return {
            "status": "ready" if self.is_ready else "not_ready",
            "checks": self.checks,
        }


class HealthCheckService:
    """Checks database, metastore, Prefect, and Marimo availability."""

    _REQUEST_TIMEOUT_SECONDS = 2.0

    def __init__(
        self,
        database_check: Callable[[], bool] = DatabaseConnection.check_connectivity,
        metastore_check: Callable[[], bool] = manager.check_connectivity,
        prefect_internal_url: str = PREFECT_INTERNAL_URL,
        marimo_internal_url: str = MARIMO_INTERNAL_URL,
    ) -> None:
        self._database_check = database_check
        self._metastore_check = metastore_check
        self._prefect_health_url = f"{prefect_internal_url.rstrip('/')}/api/health"
        self._marimo_health_url = f"{marimo_internal_url.rstrip('/')}/marimo/"

    async def readiness(self) -> HealthReport:
        """Check all required dependencies concurrently."""
        database, metastore, prefect, marimo = await asyncio.gather(
            asyncio.to_thread(self._run_sync_check, "database", self._database_check),
            asyncio.to_thread(self._run_sync_check, "metastore", self._metastore_check),
            self._run_http_check("prefect", self._prefect_health_url),
            self._run_http_check("marimo", self._marimo_health_url),
        )
        return HealthReport(
            checks={
                "database": database,
                "metastore": metastore,
                "prefect": prefect,
                "marimo": marimo,
            }
        )

    @staticmethod
    def _run_sync_check(name: str, check: Callable[[], bool]) -> str:
        try:
            return "up" if check() else "down"
        except Exception as exc:
            _log.debug("%s readiness check failed: %s", name, exc)
            return "down"

    async def _run_http_check(self, name: str, url: str) -> str:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self._REQUEST_TIMEOUT_SECONDS,
            ) as client:
                response = await client.get(url)
            return "up" if 200 <= response.status_code < 400 else "down"
        except Exception as exc:
            _log.debug("%s readiness check failed: %s", name, exc)
            return "down"


health_service = HealthCheckService()
