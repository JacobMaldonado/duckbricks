"""Tests for runtime health reporting."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.health import create_health_router
from app.services.health import HealthCheckService, HealthReport


@pytest.mark.asyncio
async def test_readiness_reports_all_dependencies_up() -> None:
    service = HealthCheckService(database_check=lambda: True, metastore_check=lambda: True)
    with patch.object(
        service,
        "_run_http_check",
        new=AsyncMock(side_effect=["up", "up"]),
    ):
        report = await service.readiness()

    assert report.is_ready is True
    assert report.as_dict()["status"] == "ready"
    assert all(status == "up" for status in report.checks.values())


@pytest.mark.asyncio
async def test_readiness_converts_dependency_exceptions_to_down() -> None:
    def failing_database_check() -> bool:
        raise RuntimeError("connection contains a secret")

    service = HealthCheckService(
        database_check=failing_database_check,
        metastore_check=lambda: True,
    )
    with patch.object(
        service,
        "_run_http_check",
        new=AsyncMock(side_effect=["up", "down"]),
    ):
        report = await service.readiness()

    assert report.is_ready is False
    assert report.checks == {
        "database": "down",
        "metastore": "up",
        "prefect": "up",
        "marimo": "down",
    }
    assert "secret" not in str(report.as_dict())


def _build_health_client(report: HealthReport) -> tuple[TestClient, AsyncMock]:
    service = AsyncMock(spec=HealthCheckService)
    service.readiness.return_value = report
    api = FastAPI()
    api.include_router(create_health_router(service))
    return TestClient(api), service


def test_liveness_does_not_call_dependencies() -> None:
    client, service = _build_health_client(HealthReport(checks={"database": "down"}))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    service.readiness.assert_not_awaited()


def test_ready_endpoint_returns_200_when_dependencies_are_up() -> None:
    report = HealthReport(checks={"database": "up", "metastore": "up"})
    client, _service = _build_health_client(report)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_endpoint_returns_503_when_a_dependency_is_down() -> None:
    report = HealthReport(checks={"database": "up", "metastore": "down"})
    client, _service = _build_health_client(report)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "up", "metastore": "down"},
    }
