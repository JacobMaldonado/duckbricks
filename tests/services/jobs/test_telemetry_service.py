"""Tests for framework-neutral Prefect telemetry aggregation."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.jobs.telemetry_service import JobTelemetryService


def _flow_run(deployment_id, state: str, *, scheduled: bool = False):
    run = MagicMock()
    run.id = uuid4()
    run.deployment_id = deployment_id
    run.name = f"{state.lower()}-run"
    run.state_name = state
    run.start_time = None if scheduled else datetime.now(UTC)
    run.end_time = None
    run.expected_start_time = datetime.now(UTC) + timedelta(hours=1)
    run.total_run_time = timedelta(seconds=12) if not scheduled else None
    run.run_count = 1
    return run


@pytest.mark.asyncio
async def test_groups_latest_and_next_runs_by_job() -> None:
    deployment_id = uuid4()
    job = MagicMock(id=7, prefect_deployment_id=str(deployment_id))
    api = MagicMock()
    api.list_runs_for_deployments = AsyncMock(return_value=[_flow_run(deployment_id, "COMPLETED")])
    api.list_scheduled_runs = AsyncMock(
        return_value=[_flow_run(deployment_id, "SCHEDULED", scheduled=True)]
    )

    result = await JobTelemetryService(api).load_dashboard([job])

    assert result[7].latest_run is not None
    assert result[7].latest_run.state == "COMPLETED"
    assert result[7].next_run is not None
    assert result[7].next_run.state == "SCHEDULED"


@pytest.mark.asyncio
async def test_jobs_without_deployments_return_empty_telemetry_without_api_calls() -> None:
    job = MagicMock(id=8, prefect_deployment_id=None)
    api = MagicMock()

    result = await JobTelemetryService(api).load_dashboard([job])

    assert result[8].latest_run is None
    api.list_runs_for_deployments.assert_not_called()
