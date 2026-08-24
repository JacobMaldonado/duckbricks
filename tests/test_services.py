"""Tests for DuckBricks services."""

from unittest.mock import Mock

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
    assert "catalog_backend" in status
    assert "data_path" in status
    assert "ducklake_name" in status
    assert status["initialized"] is False


def test_ducklake_manager_connectivity_requires_initialization(ducklake_manager):
    assert ducklake_manager.check_connectivity() is False


def test_ducklake_manager_connectivity_executes_probe(ducklake_manager):
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (1,)
    ducklake_manager._conn = connection
    ducklake_manager._initialized = True

    assert ducklake_manager.check_connectivity() is True
    connection.execute.assert_called_once_with("SELECT 1")
