"""Tests for the start_marimo startup wrapper."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch


def _load_module():
    """Import start_marimo directly from its source file."""
    path = Path(__file__).parents[2] / "app" / "helpers" / "start_marimo.py"
    spec = importlib.util.spec_from_file_location("start_marimo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_patch_converts_object_user_to_dict():
    class FakeUser:
        def __init__(self):
            self.username = "anonymous"
            self.is_authenticated = True

    fake_http_request = MagicMock()
    fake_http_request.user = FakeUser()

    fake_from_request = MagicMock(return_value=fake_http_request)

    with patch.dict(
        "sys.modules",
        {
            "marimo": MagicMock(),
            "marimo._runtime": MagicMock(),
            "marimo._runtime.commands": MagicMock(),
        },
    ):
        import sys

        commands_mock = sys.modules["marimo._runtime.commands"]
        commands_mock.HTTPRequest = MagicMock()
        commands_mock.HTTPRequest.from_request = fake_from_request

        module = _load_module()
        module.patch_http_request_user_serialization()

        patched = commands_mock.HTTPRequest.from_request
        result = patched(MagicMock())

    assert isinstance(result.user, dict)
    assert result.user.get("username") == "anonymous"


def test_patch_leaves_dict_user_unchanged():
    fake_http_request = MagicMock()
    fake_http_request.user = {"username": "admin"}

    fake_from_request = MagicMock(return_value=fake_http_request)

    with patch.dict(
        "sys.modules",
        {
            "marimo": MagicMock(),
            "marimo._runtime": MagicMock(),
            "marimo._runtime.commands": MagicMock(),
        },
    ):
        import sys

        commands_mock = sys.modules["marimo._runtime.commands"]
        commands_mock.HTTPRequest = MagicMock()
        commands_mock.HTTPRequest.from_request = fake_from_request

        module = _load_module()
        module.patch_http_request_user_serialization()

        patched = commands_mock.HTTPRequest.from_request
        result = patched(MagicMock())

    assert result.user == {"username": "admin"}


def test_patch_leaves_none_user_unchanged():
    fake_http_request = MagicMock()
    fake_http_request.user = None

    fake_from_request = MagicMock(return_value=fake_http_request)

    with patch.dict(
        "sys.modules",
        {
            "marimo": MagicMock(),
            "marimo._runtime": MagicMock(),
            "marimo._runtime.commands": MagicMock(),
        },
    ):
        import sys

        commands_mock = sys.modules["marimo._runtime.commands"]
        commands_mock.HTTPRequest = MagicMock()
        commands_mock.HTTPRequest.from_request = fake_from_request

        module = _load_module()
        module.patch_http_request_user_serialization()

        patched = commands_mock.HTTPRequest.from_request
        result = patched(MagicMock())

    assert result.user is None


def test_patch_falls_back_to_empty_dict_when_vars_raises():
    class UnvarableUser:
        __slots__ = ()

    fake_http_request = MagicMock()
    fake_http_request.user = UnvarableUser()

    fake_from_request = MagicMock(return_value=fake_http_request)

    with patch.dict(
        "sys.modules",
        {
            "marimo": MagicMock(),
            "marimo._runtime": MagicMock(),
            "marimo._runtime.commands": MagicMock(),
        },
    ):
        import sys

        commands_mock = sys.modules["marimo._runtime.commands"]
        commands_mock.HTTPRequest = MagicMock()
        commands_mock.HTTPRequest.from_request = fake_from_request

        module = _load_module()
        module.patch_http_request_user_serialization()

        patched = commands_mock.HTTPRequest.from_request
        result = patched(MagicMock())

    assert result.user == {}
