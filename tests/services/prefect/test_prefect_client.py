"""Tests for PrefectApiClient — covers deployment and run management with mocked Prefect."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from prefect.exceptions import ObjectNotFound

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
    schedule_timezone: str = "UTC",
) -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.name = name
    job.description = description
    job.schedule_cron = schedule_cron
    job.is_enabled = is_enabled
    job.prefect_deployment_id = prefect_deployment_id
    job.schedule_timezone = schedule_timezone
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
        mock_client.read_work_pool.side_effect = ObjectNotFound(Exception("404"))
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            await PrefectApiClient().ensure_work_pool()
        mock_client.create_work_pool.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_create_work_pool_when_it_already_exists(self):
        mock_client = AsyncMock()
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            await PrefectApiClient().ensure_work_pool()
        mock_client.read_work_pool.assert_awaited_once()
        mock_client.create_work_pool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_propagates_connectivity_errors(self):
        mock_client = AsyncMock()
        mock_client.read_work_pool.side_effect = RuntimeError("server unavailable")
        with (
            patch(
                "app.services.prefect.client.get_client",
                return_value=_make_client_context(mock_client),
            ),
            pytest.raises(RuntimeError, match="server unavailable"),
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
    async def test_attaches_the_selected_schedule_timezone(self):
        mock_client = AsyncMock()
        mock_client.create_flow_from_name.return_value = _FLOW_ID
        mock_client.create_deployment.return_value = _DEPLOYMENT_ID
        job = _make_job(
            schedule_cron="0 6 * * *",
            schedule_timezone="America/Mexico_City",
        )
        with patch(
            "app.services.prefect.client.get_client", return_value=_make_client_context(mock_client)
        ):
            await PrefectApiClient().create_deployment(job)
        schedule = mock_client.create_deployment.call_args.kwargs["schedules"][0].schedule
        assert schedule.timezone == "America/Mexico_City"

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

    @pytest.mark.asyncio
    async def test_lists_upcoming_runs_for_multiple_deployments(self):
        mock_client = AsyncMock()
        expected_runs = [MagicMock(expected_start_time=None)]
        mock_client.get_scheduled_flow_runs_for_deployments.return_value = expected_runs
        with patch(
            "app.services.prefect.client.get_client",
            return_value=_make_client_context(mock_client),
        ):
            result = await PrefectApiClient().list_scheduled_runs([_DEPLOYMENT_ID])
        assert result == expected_runs
        mock_client.get_scheduled_flow_runs_for_deployments.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lists_task_runs_for_a_flow_run(self):
        mock_client = AsyncMock()
        expected_runs = [MagicMock()]
        mock_client.read_task_runs.return_value = expected_runs
        with patch(
            "app.services.prefect.client.get_client",
            return_value=_make_client_context(mock_client),
        ):
            result = await PrefectApiClient().list_task_runs(_FLOW_RUN_ID)
        assert result == expected_runs
        task_filter = mock_client.read_task_runs.call_args.kwargs["task_run_filter"]
        assert task_filter.flow_run_id.any_ == [_FLOW_RUN_ID]

    @pytest.mark.asyncio
    async def test_lists_logs_for_a_flow_run(self):
        mock_client = AsyncMock()
        expected_logs = [MagicMock()]
        mock_client.read_logs.return_value = expected_logs
        with patch(
            "app.services.prefect.client.get_client",
            return_value=_make_client_context(mock_client),
        ):
            result = await PrefectApiClient().list_logs(_FLOW_RUN_ID)
        assert result == expected_logs
        log_filter = mock_client.read_logs.call_args.kwargs["log_filter"]
        assert log_filter.flow_run_id.any_ == [_FLOW_RUN_ID]


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
