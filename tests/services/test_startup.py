"""Tests for fail-fast application startup orchestration."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.services.startup import ApplicationStartup


@pytest.mark.asyncio
async def test_startup_initializes_dependencies_in_order(tmp_path) -> None:
    calls: list[str] = []
    validator = Mock(side_effect=lambda: calls.append("configuration"))
    database = Mock(side_effect=lambda: calls.append("database"))
    metastore = Mock()
    metastore.initialize.side_effect = lambda: calls.append("metastore")
    prefect = Mock()
    prefect.ensure_work_pool = AsyncMock(side_effect=lambda: calls.append("prefect"))
    workspace = tmp_path / "workspace"

    startup = ApplicationStartup(
        workspace_path=str(workspace),
        configuration_validator=validator,
        database_initializer=database,
        metastore_initializer=metastore,
        prefect_initializer=prefect,
        retry_delay_seconds=0,
    )

    await startup.run()

    assert calls == ["configuration", "database", "metastore", "prefect"]
    assert workspace.is_dir()


@pytest.mark.asyncio
async def test_startup_retries_transient_dependency_failure(tmp_path) -> None:
    database = Mock(side_effect=[RuntimeError("temporary"), None])
    metastore = Mock()
    prefect = Mock()
    prefect.ensure_work_pool = AsyncMock()
    startup = ApplicationStartup(
        workspace_path=str(tmp_path),
        configuration_validator=Mock(),
        database_initializer=database,
        metastore_initializer=metastore,
        prefect_initializer=prefect,
        dependency_attempts=2,
        retry_delay_seconds=0,
    )

    await startup.run()

    assert database.call_count == 2
    metastore.initialize.assert_called_once()
    prefect.ensure_work_pool.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_raises_sanitized_error_after_retries(tmp_path) -> None:
    secret = "postgresql://user:super-secret@postgres/database"
    startup = ApplicationStartup(
        workspace_path=str(tmp_path),
        configuration_validator=Mock(),
        database_initializer=Mock(side_effect=RuntimeError(secret)),
        metastore_initializer=Mock(),
        prefect_initializer=Mock(),
        dependency_attempts=2,
        retry_delay_seconds=0,
    )

    with pytest.raises(RuntimeError, match="Required dependency initialization failed") as error:
        await startup.run()

    assert secret not in str(error.value)


@pytest.mark.asyncio
async def test_invalid_configuration_stops_before_creating_workspace(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    startup = ApplicationStartup(
        workspace_path=str(workspace),
        configuration_validator=Mock(side_effect=ValueError("invalid")),
        database_initializer=Mock(),
        metastore_initializer=Mock(),
        prefect_initializer=Mock(),
        retry_delay_seconds=0,
    )

    with pytest.raises(ValueError, match="invalid"):
        await startup.run()

    assert not workspace.exists()
