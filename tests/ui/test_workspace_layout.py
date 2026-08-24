"""Regression tests for the workspace editor layout contract."""

from __future__ import annotations

import re

import pytest

from app.ui.workspace_layout import (
    WORKSPACE_CODEMIRROR_LAYOUT_CSS,
    WORKSPACE_VIEWPORT_STYLE,
)


def _css_declarations(selector: str) -> dict[str, str]:
    match = re.search(
        rf"{re.escape(selector)}\s*\{{(?P<declarations>[^}}]+)\}}",
        WORKSPACE_CODEMIRROR_LAYOUT_CSS,
    )
    assert match is not None

    declarations: dict[str, str] = {}
    for declaration in match.group("declarations").split(";"):
        if ":" not in declaration:
            continue
        property_name, value = declaration.split(":", maxsplit=1)
        declarations[property_name.strip()] = value.strip()
    return declarations


def test_workspace_uses_documented_full_viewport_height() -> None:
    assert WORKSPACE_VIEWPORT_STYLE == "height: calc(100vh - 64px)"


@pytest.mark.parametrize(
    "selector",
    [
        ".ws-editor .nicegui-codemirror",
        ".ws-editor .cm-editor",
        ".ws-editor .cm-scroller",
    ],
)
def test_codemirror_height_chain_fills_editor_panel(selector: str) -> None:
    declarations = _css_declarations(selector)

    assert declarations["height"] == "100% !important"
    assert declarations["min-height"] == "0 !important"


def test_codemirror_panel_consumes_remaining_editor_space() -> None:
    declarations = _css_declarations(".ws-codemirror-panel")

    assert declarations["flex"] == "1 1 0% !important"
    assert declarations["width"] == "100% !important"
    assert declarations["min-height"] == "0 !important"


def test_codemirror_layout_does_not_restore_content_height() -> None:
    assert "height: auto" not in WORKSPACE_CODEMIRROR_LAYOUT_CSS
