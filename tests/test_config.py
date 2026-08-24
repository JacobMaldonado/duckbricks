"""Tests for runtime configuration validation."""

from dataclasses import replace
from typing import Any, cast

import pytest

from app.config import ConfigurationError, RuntimeConfiguration, validate_runtime_configuration


def _replace_configuration(
    configuration: RuntimeConfiguration,
    updates: dict[str, object],
) -> RuntimeConfiguration:
    untyped_replace = cast(Any, replace)
    return cast(RuntimeConfiguration, untyped_replace(configuration, **updates))


@pytest.fixture
def valid_configuration() -> RuntimeConfiguration:
    return RuntimeConfiguration(
        database_url="postgresql://duckbricks:secret@postgres:5432/duckbricks",
        storage_backend="local",
        data_path="/data/parquet/",
        ducklake_pg_host="postgres",
        ducklake_pg_port=5432,
        ducklake_pg_database="duckbricks",
        ducklake_pg_user="duckbricks",
        ducklake_pg_password="secret",
        marimo_internal_url="http://marimo:2718",
        prefect_internal_url="http://prefect-server:4200",
        prefect_external_url="http://localhost:4200",
    )


def test_valid_configuration_passes(valid_configuration: RuntimeConfiguration) -> None:
    validate_runtime_configuration(valid_configuration)


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("database_url", "not-a-url", "DATABASE_URL"),
        ("ducklake_pg_host", "", "DUCKLAKE_PG_HOST"),
        ("ducklake_pg_port", 70000, "DUCKLAKE_PG_PORT"),
        ("marimo_internal_url", "marimo:2718", "MARIMO_INTERNAL_URL"),
        ("prefect_internal_url", "", "PREFECT_INTERNAL_URL"),
        ("storage_backend", "unknown", "DUCKBRICKS_STORAGE_BACKEND"),
        ("data_path", "", "DUCKBRICKS_DATA_PATH"),
    ],
)
def test_invalid_configuration_reports_actionable_field(
    valid_configuration: RuntimeConfiguration,
    field: str,
    value: object,
    expected_message: str,
) -> None:
    configuration = _replace_configuration(valid_configuration, {field: value})

    with pytest.raises(ConfigurationError, match=expected_message):
        validate_runtime_configuration(configuration)


@pytest.mark.parametrize(
    ("backend", "updates", "missing_variable"),
    [
        ("s3", {}, "AWS_ACCESS_KEY_ID"),
        (
            "minio",
            {"aws_access_key_id": "key", "aws_secret_access_key": "secret"},
            "MINIO_ENDPOINT",
        ),
        (
            "r2",
            {"aws_access_key_id": "key", "aws_secret_access_key": "secret"},
            "R2_ACCOUNT_ID",
        ),
        ("gcs", {}, "GCS_KEY_ID"),
        ("azure", {}, "AZURE_ACCOUNT"),
    ],
)
def test_remote_storage_requires_backend_credentials(
    valid_configuration: RuntimeConfiguration,
    backend: str,
    updates: dict[str, str],
    missing_variable: str,
) -> None:
    configuration_updates: dict[str, object] = {
        "storage_backend": backend,
        "data_path": "s3://duckbricks/data/",
    }
    configuration_updates.update(updates)
    configuration = _replace_configuration(valid_configuration, configuration_updates)

    with pytest.raises(ConfigurationError, match=missing_variable):
        validate_runtime_configuration(configuration)


def test_validation_error_does_not_include_secret_values(
    valid_configuration: RuntimeConfiguration,
) -> None:
    secret = "do-not-leak-this-value"
    configuration = replace(
        valid_configuration,
        storage_backend="minio",
        aws_access_key_id="key",
        aws_secret_access_key=secret,
        minio_endpoint="invalid-url",
    )

    with pytest.raises(ConfigurationError) as error:
        validate_runtime_configuration(configuration)

    assert secret not in str(error.value)
