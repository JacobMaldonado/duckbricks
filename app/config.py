"""DuckBricks configuration."""

import os
from importlib.metadata import version as _pkg_version

from dotenv import load_dotenv

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
