"""Backward-compatible re-export. Prefer app.services.metastore."""

from app.services.metastore import manager
from app.services.metastore.ducklake_manager import MetastoreManager as DuckLakeManager

__all__ = ["DuckLakeManager", "manager"]
