"""DuckBricks configuration."""

import os
from dataclasses import dataclass
from importlib.metadata import version as _pkg_version
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

load_dotenv()

try:
    VERSION = _pkg_version("duckbricks")
except Exception:
    VERSION = "0.1.3"

DATA_PATH = os.getenv("DUCKBRICKS_DATA_PATH", "/data/parquet/")
DUCKLAKE_NAME = os.getenv("DUCKBRICKS_DUCKLAKE_NAME", "duckbricks")
STORAGE_BACKEND: str = os.getenv("DUCKBRICKS_STORAGE_BACKEND", "local")

# S3 / MinIO / R2
AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "")
R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")

# GCS
GCS_KEY_ID: str = os.getenv("GCS_KEY_ID", "")
GCS_SECRET: str = os.getenv("GCS_SECRET", "")

# Azure
AZURE_CONNECTION_STRING: str = os.getenv("AZURE_CONNECTION_STRING", "")
AZURE_ACCOUNT: str = os.getenv("AZURE_ACCOUNT", "")
AZURE_KEY: str = os.getenv("AZURE_KEY", "")

DUCKLAKE_PG_HOST: str = os.getenv("DUCKLAKE_PG_HOST", "localhost")
DUCKLAKE_PG_PORT: int = int(os.getenv("DUCKLAKE_PG_PORT", "5432"))
DUCKLAKE_PG_DATABASE: str = os.getenv("DUCKLAKE_PG_DATABASE", "duckbricks")
DUCKLAKE_PG_USER: str = os.getenv("DUCKLAKE_PG_USER", "duckbricks")
DUCKLAKE_PG_PASSWORD: str = os.getenv("DUCKLAKE_PG_PASSWORD", "duckbricks")

HOST = os.getenv("DUCKBRICKS_HOST", "0.0.0.0")
PORT = int(os.getenv("DUCKBRICKS_PORT", "8000"))

ENV = os.getenv("DUCKBRICKS_ENV", "production")
RELOAD = ENV == "development"

DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://duckbricks:duckbricks@localhost:5432/duckbricks"
)

WORKSPACE_PATH: str = os.getenv("DUCKBRICKS_WORKSPACE_PATH", "./workspace")

MARIMO_URL: str = os.getenv("MARIMO_URL", "/marimo")
MARIMO_INTERNAL_URL: str = os.getenv("MARIMO_INTERNAL_URL", "http://localhost:2718")

PREFECT_INTERNAL_URL: str = os.getenv("PREFECT_INTERNAL_URL", "http://localhost:4200")
PREFECT_EXTERNAL_URL: str = os.getenv("PREFECT_EXTERNAL_URL", "http://localhost:4200")
PREFECT_UI_BASE_PATH: str = "/prefect-ui"

SECRET_KEY: str = os.getenv("DUCKBRICKS_SECRET_KEY", "")


class ConfigurationError(ValueError):
    """Raised when the runtime configuration is incomplete or invalid."""


@dataclass(frozen=True)
class RuntimeConfiguration:
    """Configuration values required to initialize the DuckBricks runtime."""

    database_url: str
    storage_backend: str
    data_path: str
    ducklake_pg_host: str
    ducklake_pg_port: int
    ducklake_pg_database: str
    ducklake_pg_user: str
    ducklake_pg_password: str
    marimo_internal_url: str
    prefect_internal_url: str
    prefect_external_url: str
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    minio_endpoint: str = ""
    r2_account_id: str = ""
    gcs_key_id: str = ""
    gcs_secret: str = ""
    azure_connection_string: str = ""
    azure_account: str = ""
    azure_key: str = ""

    @classmethod
    def current(cls) -> "RuntimeConfiguration":
        """Build a snapshot from the module-level environment configuration."""
        return cls(
            database_url=DATABASE_URL,
            storage_backend=STORAGE_BACKEND,
            data_path=DATA_PATH,
            ducklake_pg_host=DUCKLAKE_PG_HOST,
            ducklake_pg_port=DUCKLAKE_PG_PORT,
            ducklake_pg_database=DUCKLAKE_PG_DATABASE,
            ducklake_pg_user=DUCKLAKE_PG_USER,
            ducklake_pg_password=DUCKLAKE_PG_PASSWORD,
            marimo_internal_url=MARIMO_INTERNAL_URL,
            prefect_internal_url=PREFECT_INTERNAL_URL,
            prefect_external_url=PREFECT_EXTERNAL_URL,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            minio_endpoint=MINIO_ENDPOINT,
            r2_account_id=R2_ACCOUNT_ID,
            gcs_key_id=GCS_KEY_ID,
            gcs_secret=GCS_SECRET,
            azure_connection_string=AZURE_CONNECTION_STRING,
            azure_account=AZURE_ACCOUNT,
            azure_key=AZURE_KEY,
        )


class RuntimeConfigurationValidator:
    """Validates configuration before any runtime dependency is initialized."""

    _SUPPORTED_STORAGE_BACKENDS = frozenset({"local", "s3", "minio", "r2", "gcs", "azure"})

    def __init__(self, configuration: RuntimeConfiguration) -> None:
        self._configuration = configuration

    def validate(self) -> None:
        """Raise ConfigurationError with actionable, secret-free validation details."""
        errors: list[str] = []
        self._validate_database_url(errors)
        self._validate_ducklake_connection(errors)
        self._validate_service_urls(errors)
        self._validate_storage(errors)
        if errors:
            details = "; ".join(errors)
            raise ConfigurationError(f"Invalid DuckBricks configuration: {details}")

    def _validate_database_url(self, errors: list[str]) -> None:
        try:
            database_url = make_url(self._configuration.database_url)
        except ArgumentError:
            errors.append("DATABASE_URL is not a valid database URL")
            return
        if database_url.get_backend_name() != "postgresql":
            errors.append("DATABASE_URL must use PostgreSQL")
        if not database_url.host:
            errors.append("DATABASE_URL must include a host")
        if not database_url.database:
            errors.append("DATABASE_URL must include a database name")

    def _validate_ducklake_connection(self, errors: list[str]) -> None:
        required_values = {
            "DUCKLAKE_PG_HOST": self._configuration.ducklake_pg_host,
            "DUCKLAKE_PG_DATABASE": self._configuration.ducklake_pg_database,
            "DUCKLAKE_PG_USER": self._configuration.ducklake_pg_user,
            "DUCKLAKE_PG_PASSWORD": self._configuration.ducklake_pg_password,
        }
        self._require_values(required_values, errors)
        port = self._configuration.ducklake_pg_port
        if port < 1 or port > 65535:
            errors.append("DUCKLAKE_PG_PORT must be between 1 and 65535")

    def _validate_service_urls(self, errors: list[str]) -> None:
        service_urls = {
            "MARIMO_INTERNAL_URL": self._configuration.marimo_internal_url,
            "PREFECT_INTERNAL_URL": self._configuration.prefect_internal_url,
            "PREFECT_EXTERNAL_URL": self._configuration.prefect_external_url,
        }
        for name, value in service_urls.items():
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"{name} must be an absolute HTTP(S) URL")

    def _validate_storage(self, errors: list[str]) -> None:
        backend = self._configuration.storage_backend.lower()
        if backend not in self._SUPPORTED_STORAGE_BACKENDS:
            supported = ", ".join(sorted(self._SUPPORTED_STORAGE_BACKENDS))
            errors.append(f"DUCKBRICKS_STORAGE_BACKEND must be one of: {supported}")
            return
        if not self._configuration.data_path.strip():
            errors.append("DUCKBRICKS_DATA_PATH must not be empty")
        if backend in {"s3", "minio", "r2"}:
            self._require_values(
                {
                    "AWS_ACCESS_KEY_ID": self._configuration.aws_access_key_id,
                    "AWS_SECRET_ACCESS_KEY": self._configuration.aws_secret_access_key,
                },
                errors,
            )
        if backend == "minio":
            self._require_values({"MINIO_ENDPOINT": self._configuration.minio_endpoint}, errors)
            self._validate_optional_http_url(
                "MINIO_ENDPOINT", self._configuration.minio_endpoint, errors
            )
        elif backend == "r2":
            self._require_values({"R2_ACCOUNT_ID": self._configuration.r2_account_id}, errors)
        elif backend == "gcs":
            self._require_values(
                {
                    "GCS_KEY_ID": self._configuration.gcs_key_id,
                    "GCS_SECRET": self._configuration.gcs_secret,
                },
                errors,
            )
        elif backend == "azure" and not self._configuration.azure_connection_string:
            self._require_values(
                {
                    "AZURE_ACCOUNT": self._configuration.azure_account,
                    "AZURE_KEY": self._configuration.azure_key,
                },
                errors,
            )

    @staticmethod
    def _require_values(values: dict[str, str], errors: list[str]) -> None:
        for name, value in values.items():
            if not value.strip():
                errors.append(f"{name} must not be empty")

    @staticmethod
    def _validate_optional_http_url(name: str, value: str, errors: list[str]) -> None:
        if not value:
            return
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{name} must be an absolute HTTP(S) URL")


def validate_runtime_configuration(
    configuration: RuntimeConfiguration | None = None,
) -> None:
    """Validate the current runtime configuration or an explicit snapshot."""
    RuntimeConfigurationValidator(configuration or RuntimeConfiguration.current()).validate()
