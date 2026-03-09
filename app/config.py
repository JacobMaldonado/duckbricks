"""DuckBricks configuration."""

import os
from importlib.metadata import version as _pkg_version

# Version (reads from pyproject.toml via installed package metadata)
try:
    VERSION = _pkg_version("duckbricks")
except Exception:
    VERSION = "0.1.3"

# Paths
CATALOG_PATH = os.getenv("DUCKBRICKS_CATALOG_PATH", "/data/metastore.ducklake")
DATA_PATH = os.getenv("DUCKBRICKS_DATA_PATH", "/data/parquet/")
DUCKLAKE_NAME = os.getenv("DUCKBRICKS_DUCKLAKE_NAME", "duckbricks")

# Server
HOST = os.getenv("DUCKBRICKS_HOST", "0.0.0.0")
PORT = int(os.getenv("DUCKBRICKS_PORT", "8000"))
