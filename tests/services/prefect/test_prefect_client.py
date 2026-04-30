"""Tests for PrefectApiClient — covers deployment and run management with mocked Prefect."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.prefect.client import PrefectApiClient

_DEPLOYMENT_ID = uuid4()
_FLOW_RUN_ID = uuid4()
_FLOW_ID = uuid4()
_JOB_ID = 42


def _make_job(
    job_id: int = _JOB_ID,
    name: str = "Daily ETL",
    description: str | None = "Test job",
    schedule_cron: str | None = None,
    is_enabled: bool = True,
    prefect_deployment_id: str | None = None,
) -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.name = name
    job.description = description
    job.schedule_cron = schedule_cron
    job.is_enabled = is_enabled
    job.prefect_deployment_id = prefect_deployment_id
    return job


def _make_client_context(mock_client: AsyncMock) -> MagicMock:
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=mock_client)
    context.__aexit__ = AsyncMock(return_value=None)
    return context


class TestEnsureWorkPool:
    @pytest.mark.asyncio
    async def test_creates_work_pool_when_absent(self):
        mock_client = AsyncMock()
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            await PrefectApiClient().ensure_work_pool()
        mock_client.create_work_pool.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_swallows_exception_when_pool_already_exists(self):
        mock_client = AsyncMock()
        mock_client.create_work_pool.side_effect = Exception("already exists")
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            await PrefectApiClient().ensure_work_pool()


class TestRegisterFlow:
    @pytest.mark.asyncio
    async def test_returns_flow_id_from_prefect(self):
        mock_client = AsyncMock()
        mock_client.create_flow_from_name.return_value = _FLOW_ID
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            result = await PrefectApiClient().register_flow()
        assert result == _FLOW_ID


class TestCreateDeployment:
    @pytest.mark.asyncio
    async def test_creates_deployment_and_returns_id(self):
        mock_client = AsyncMock()
        mock_client.create_flow_from_name.return_value = _FLOW_ID
        mock_client.create_deployment.return_value = _DEPLOYMENT_ID
        job = _make_job()
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            result = await PrefectApiClient().create_deployment(job)
        assert result == _DEPLOYMENT_ID
        mock_client.create_deployment.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_attaches_cron_schedule_when_enabled_and_cron_set(self):
        mock_client = AsyncMock()
        mock_client.create_flow_from_name.return_value = _FLOW_ID
        mock_client.create_deployment.return_value = _DEPLOYMENT_ID
        job = _make_job(schedule_cron="0 6 * * *", is_enabled=True)
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            await PrefectApiClient().create_deployment(job)
        call_kwargs = mock_client.create_deployment.call_args.kwargs
        assert len(call_kwargs["schedules"]) == 1

    @pytest.mark.asyncio
    async def test_omits_schedule_when_job_is_disabled(self):
        mock_client = AsyncMock()
        mock_client.create_flow_from_name.return_value = _FLOW_ID
        mock_client.create_deployment.return_value = _DEPLOYMENT_ID
        job = _make_job(schedule_cron="0 6 * * *", is_enabled=False)
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            await PrefectApiClient().create_deployment(job)
        call_kwargs = mock_client.create_deployment.call_args.kwargs
        assert call_kwargs["schedules"] == []

    @pytest.mark.asyncio
    async def test_omits_schedule_when_no_cron_configured(self):
        mock_client = AsyncMock()
        mock_client.create_flow_from_name.return_value = _FLOW_ID
        mock_client.create_deployment.return_value = _DEPLOYMENT_ID
        job = _make_job(schedule_cron=None, is_enabled=True)
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            await PrefectApiClient().create_deployment(job)
        call_kwargs = mock_client.create_deployment.call_args.kwargs
        assert call_kwargs["schedules"] == []


class TestDeleteDeployment:
    @pytest.mark.asyncio
    async def test_deletes_deployment_by_id(self):
        mock_client = AsyncMock()
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            await PrefectApiClient().delete_deployment(_DEPLOYMENT_ID)
        mock_client.delete_deployment.assert_awaited_once_with(_DEPLOYMENT_ID)


class TestTriggerRun:
    @pytest.mark.asyncio
    async def test_returns_flow_run_from_prefect(self):
        mock_client = AsyncMock()
        expected_run = MagicMock()
        expected_run.id = _FLOW_RUN_ID
        mock_client.create_flow_run_from_deployment.return_value = expected_run
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            result = await PrefectApiClient().trigger_run(_DEPLOYMENT_ID)
        assert result == expected_run
        mock_client.create_flow_run_from_deployment.assert_awaited_once_with(_DEPLOYMENT_ID)


class TestListRuns:
    @pytest.mark.asyncio
    async def test_returns_list_of_flow_runs(self):
        mock_client = AsyncMock()
        expected_runs = [MagicMock(), MagicMock()]
        mock_client.read_flow_runs.return_value = expected_runs
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            result = await PrefectApiClient().list_runs(_DEPLOYMENT_ID)
        assert result == expected_runs


class TestUiPaths:
    def test_deployment_ui_url_format(self):
        client = PrefectApiClient()
        url = client.deployment_ui_url(_DEPLOYMENT_ID)
        assert str(_DEPLOYMENT_ID) in url
        assert "deployments" in url

    def test_run_ui_url_format(self):
        client = PrefectApiClient()
        url = client.run_ui_url(_FLOW_RUN_ID)
        assert str(_FLOW_RUN_ID) in url
        assert "flow-run" in url


class TestDeploymentName:
    def test_sanitizes_spaces_in_job_name(self):
        name = PrefectApiClient._deployment_name(1, "My Daily ETL Job")
        assert " " not in name
        assert "1" in name

    def test_truncates_long_job_names(self):
        long_name = "a" * 100
        name = PrefectApiClient._deployment_name(1, long_name)
        assert len(name) <= 60
