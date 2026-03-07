"""Shared test fixtures."""

import pytest


@pytest.fixture
def ducklake_manager():
    """Create a fresh DuckLakeManager instance for testing."""
    from app.services.ducklake import DuckLakeManager

    return DuckLakeManager()
