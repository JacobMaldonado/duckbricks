"""Tests for DuckBricks services."""

import pytest
import tempfile
import os

from app.services.ducklake import DuckLakeManager


def test_ducklake_manager_can_be_instantiated():
    """DuckLakeManager should instantiate without errors."""
    manager = DuckLakeManager()
    assert manager is not None
    assert manager.is_initialized is False


def test_ducklake_manager_status(ducklake_manager):
    """DuckLakeManager.status() should return expected keys."""
    status = ducklake_manager.status()
    assert "initialized" in status
    assert "catalog_path" in status
    assert "data_path" in status
    assert "ducklake_name" in status
    assert status["initialized"] is False


def test_create_catalog_requires_initialization():
    """Creating a catalog should fail if metastore is not initialized."""
    manager = DuckLakeManager()
    assert not manager.is_initialized

    with pytest.raises(RuntimeError, match="not initialized"):
        manager.create_catalog("test_catalog")


def test_create_catalog_validates_name():
    """Creating a catalog should validate the name format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = DuckLakeManager()
        # Override paths to use temp directory
        import app.services.ducklake as ducklake_module
        original_catalog = ducklake_module.CATALOG_PATH
        original_data = ducklake_module.DATA_PATH

        try:
            ducklake_module.CATALOG_PATH = os.path.join(tmpdir, "test.ducklake")
            ducklake_module.DATA_PATH = os.path.join(tmpdir, "data")
            manager.initialize()

            # Invalid names
            result = manager.create_catalog("Invalid-Name")
            assert not result["success"]
            assert "lowercase" in result["error"].lower()

            result = manager.create_catalog("Invalid Name")
            assert not result["success"]

            result = manager.create_catalog("UPPERCASE")
            assert not result["success"]

            result = manager.create_catalog("")
            assert not result["success"]

        finally:
            ducklake_module.CATALOG_PATH = original_catalog
            ducklake_module.DATA_PATH = original_data


def test_create_catalog_success():
    """Creating a catalog with valid name should succeed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = DuckLakeManager()
        import app.services.ducklake as ducklake_module
        original_catalog = ducklake_module.CATALOG_PATH
        original_data = ducklake_module.DATA_PATH

        try:
            ducklake_module.CATALOG_PATH = os.path.join(tmpdir, "test.ducklake")
            ducklake_module.DATA_PATH = os.path.join(tmpdir, "data")
            manager.initialize()

            # Valid catalog name
            result = manager.create_catalog("analytics")
            assert result["success"]
            assert "created successfully" in result["message"]

            # Verify catalog appears in list
            catalogs = manager.list_catalogs()
            assert "analytics" in catalogs

        finally:
            ducklake_module.CATALOG_PATH = original_catalog
            ducklake_module.DATA_PATH = original_data


def test_create_catalog_prevents_duplicates():
    """Creating a catalog with duplicate name should fail."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = DuckLakeManager()
        import app.services.ducklake as ducklake_module
        original_catalog = ducklake_module.CATALOG_PATH
        original_data = ducklake_module.DATA_PATH

        try:
            ducklake_module.CATALOG_PATH = os.path.join(tmpdir, "test.ducklake")
            ducklake_module.DATA_PATH = os.path.join(tmpdir, "data")
            manager.initialize()

            # Create first catalog
            result = manager.create_catalog("production")
            assert result["success"]

            # Try to create duplicate
            result = manager.create_catalog("production")
            assert not result["success"]
            assert "already exists" in result["error"]

        finally:
            ducklake_module.CATALOG_PATH = original_catalog
            ducklake_module.DATA_PATH = original_data
