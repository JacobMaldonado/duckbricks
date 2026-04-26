"""Tests for the Marimo reverse-proxy routes."""

import pytest


class TestStripHopByHopHeaders:
    def test_removes_connection_header(self):
        from app.api.marimo_proxy import strip_hop_by_hop

        headers = {"connection": "keep-alive", "content-type": "application/json"}
        result = strip_hop_by_hop(headers)
        assert "connection" not in result
        assert result["content-type"] == "application/json"

    def test_removes_all_hop_by_hop(self):
        from app.api.marimo_proxy import strip_hop_by_hop

        hop_headers = {
            "connection": "x",
            "keep-alive": "x",
            "transfer-encoding": "chunked",
            "upgrade": "websocket",
            "te": "trailers",
        }
        result = strip_hop_by_hop(hop_headers)
        assert result == {}

    def test_preserves_safe_headers(self):
        from app.api.marimo_proxy import strip_hop_by_hop

        headers = {
            "authorization": "Bearer token",
            "content-type": "text/html",
            "x-custom": "value",
        }
        result = strip_hop_by_hop(headers)
        assert result == headers

    def test_case_insensitive_removal(self):
        from app.api.marimo_proxy import strip_hop_by_hop

        headers = {"Connection": "keep-alive", "Transfer-Encoding": "chunked"}
        result = strip_hop_by_hop(headers)
        assert result == {}


class TestRequestHeaderFiltering:
    def test_accept_encoding_is_dropped(self):
        from app.api.marimo_proxy import _HEADERS_DROPPED_FROM_REQUEST

        assert "accept-encoding" in _HEADERS_DROPPED_FROM_REQUEST

    def test_host_is_dropped(self):
        from app.api.marimo_proxy import _HEADERS_DROPPED_FROM_REQUEST

        assert "host" in _HEADERS_DROPPED_FROM_REQUEST


class TestResponseHeaderFiltering:
    def test_content_encoding_is_dropped(self):
        from app.api.marimo_proxy import _HEADERS_DROPPED_FROM_RESPONSE

        assert "content-encoding" in _HEADERS_DROPPED_FROM_RESPONSE

    def test_content_length_is_dropped(self):
        from app.api.marimo_proxy import _HEADERS_DROPPED_FROM_RESPONSE

        assert "content-length" in _HEADERS_DROPPED_FROM_RESPONSE


class TestMarimoProxyConfig:
    def test_marimo_internal_url_is_configurable(self, monkeypatch):
        monkeypatch.setenv("MARIMO_INTERNAL_URL", "http://custom-host:9999")
        import importlib

        import app.config as config_module

        importlib.reload(config_module)
        assert config_module.MARIMO_INTERNAL_URL == "http://custom-host:9999"
        monkeypatch.delenv("MARIMO_INTERNAL_URL", raising=False)
        importlib.reload(config_module)

    def test_marimo_url_default_is_relative_path(self, monkeypatch):
        monkeypatch.delenv("MARIMO_URL", raising=False)
        import importlib

        import app.config as config_module

        importlib.reload(config_module)
        assert config_module.MARIMO_URL == "/marimo"
        importlib.reload(config_module)
