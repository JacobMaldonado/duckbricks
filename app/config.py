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
HELPERS_PATH: str = os.getenv("DUCKBRICKS_HELPERS_PATH", "/data/.duckbricks")

MARIMO_URL: str = os.getenv("MARIMO_URL", "http://localhost:2718")
MARIMO_TOKEN_PASSWORD: str = os.getenv("MARIMO_TOKEN_PASSWORD", "duckbricks")
