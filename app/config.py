"""DuckBricks configuration."""

import os
from pathlib import Path
from importlib.metadata import version as _pkg_version

# Version (reads from pyproject.toml via installed package metadata)
try:
    VERSION = _pkg_version("duckbricks")
except Exception:
    VERSION = "0.1.3"

# Default data directory in user's home (cross-platform)
DEFAULT_DATA_DIR = Path.home() / ".duckbricks" / "data"

# Paths (now default to user-writable directory)
CATALOG_PATH = os.getenv(
    "DUCKBRICKS_CATALOG_PATH",
    str(DEFAULT_DATA_DIR / "metastore.ducklake")
)
DATA_PATH = os.getenv(
    "DUCKBRICKS_DATA_PATH",
    str(DEFAULT_DATA_DIR / "parquet")
)
DUCKLAKE_NAME = os.getenv("DUCKBRICKS_DUCKLAKE_NAME", "duckbricks")

# Server
HOST = os.getenv("DUCKBRICKS_HOST", "0.0.0.0")
PORT = int(os.getenv("DUCKBRICKS_PORT", "8000"))
