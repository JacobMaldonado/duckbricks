"""Tests for the duckbricks_utils workspace helper module."""

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_module():
    """Import duckbricks_utils directly from its source file."""
    helpers_path = Path(__file__).parents[2] / "app" / "helpers" / "duckbricks_utils.py"
    spec = importlib.util.spec_from_file_location("duckbricks_utils", helpers_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def utils():
    return _load_module()


class TestCatalogName:
    def test_returns_default_when_env_absent(self, utils):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DUCKBRICKS_DUCKLAKE_NAME", None)
            assert utils.catalog_name() == "duckbricks"

    def test_returns_env_value_when_set(self, utils):
        with patch.dict(os.environ, {"DUCKBRICKS_DUCKLAKE_NAME": "my_catalog"}):
            assert utils.catalog_name() == "my_catalog"


class TestDataPath:
    def test_returns_default_when_env_absent(self, utils):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DUCKBRICKS_DATA_PATH", None)
            assert utils.data_path() == "/data/parquet/"

    def test_returns_env_value_when_set(self, utils):
        with patch.dict(os.environ, {"DUCKBRICKS_DATA_PATH": "/custom/path/"}):
            assert utils.data_path() == "/custom/path/"


class TestPgDsn:
    def test_builds_dsn_from_env_vars(self, utils):
        env = {
            "DUCKLAKE_PG_HOST": "my-host",
            "DUCKLAKE_PG_PORT": "5433",
            "DUCKLAKE_PG_DATABASE": "mydb",
            "DUCKLAKE_PG_USER": "myuser",
            "DUCKLAKE_PG_PASSWORD": "mysecret",
        }
        with patch.dict(os.environ, env):
            dsn = utils._pg_dsn()
        assert "host=my-host" in dsn
        assert "port=5433" in dsn
        assert "dbname=mydb" in dsn
        assert "user=myuser" in dsn
        assert "password=mysecret" in dsn

    def test_defaults_when_env_absent(self, utils):
        for key in [
            "DUCKLAKE_PG_HOST",
            "DUCKLAKE_PG_PORT",
            "DUCKLAKE_PG_DATABASE",
            "DUCKLAKE_PG_USER",
            "DUCKLAKE_PG_PASSWORD",
        ]:
            os.environ.pop(key, None)
        dsn = utils._pg_dsn()
        assert "host=localhost" in dsn
        assert "port=5432" in dsn
        assert "dbname=duckbricks" in dsn


class TestConnect:
    def test_connect_calls_duckdb_and_returns_connection(self, utils):
        mock_conn = MagicMock()
        with patch("duckdb.connect", return_value=mock_conn) as mock_duckdb:
            result = utils.connect()

        mock_duckdb.assert_called_once()
        assert result is mock_conn
        execute_calls = [str(call) for call in mock_conn.execute.call_args_list]
        assert any("ducklake" in c for c in execute_calls)
        assert any("postgres" in c for c in execute_calls)
        assert any("USE" in c for c in execute_calls)

    def test_connect_accepts_data_path_override(self, utils):
        mock_conn = MagicMock()
        with patch("duckdb.connect", return_value=mock_conn):
            utils.connect(override_data_path="/tmp/custom/")

        attach_call = next(
            str(c)
            for c in mock_conn.execute.call_args_list
            if "ATTACH" in str(c)
        )
        assert "/tmp/custom/" in attach_call
