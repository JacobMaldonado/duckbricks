"""Tests for shared application navigation behavior."""

from __future__ import annotations

import pytest

from app.ui.components.navigation import NavigationDestination, NavigationDrawerState


@pytest.mark.parametrize(
    ("current_path", "expected_active"),
    [
        ("/jobs", True),
        ("/jobs/", True),
        ("/jobs/execution/42", True),
        ("/query", False),
        ("/jobs-archive", False),
    ],
)
def test_navigation_destination_matches_route_family(
    current_path: str,
    expected_active: bool,
) -> None:
    destination = NavigationDestination(route="/jobs", label="Jobs", icon="schedule")

    assert destination.is_active(current_path) is expected_active


def test_active_destination_uses_highlight_classes() -> None:
    destination = NavigationDestination(route="/workspace", label="Workspace", icon="folder_open")

    assert "bg-blue-1" in destination.item_classes("/workspace")
    assert destination.icon_classes("/workspace") == "text-primary"
    assert "text-primary" in destination.label_classes("/workspace")


def test_inactive_destination_uses_neutral_classes() -> None:
    destination = NavigationDestination(route="/workspace", label="Workspace", icon="folder_open")

    assert "bg-blue-1" not in destination.item_classes("/query")
    assert destination.icon_classes("/query") == "text-grey-7"
    assert "text-grey-9" in destination.label_classes("/query")


def test_expanded_drawer_never_renders_as_mini() -> None:
    state = NavigationDrawerState()

    state.pointer_entered()
    assert state.should_render_mini is False

    state.pointer_left()
    assert state.should_render_mini is False


def test_compact_drawer_expands_only_while_hovered() -> None:
    state = NavigationDrawerState()
    state.set_compact(True)

    assert state.should_render_mini is True

    state.pointer_entered()
    assert state.should_render_mini is False

    state.pointer_left()
    assert state.should_render_mini is True


def test_drawer_mode_changes_only_through_explicit_toggle() -> None:
    state = NavigationDrawerState()

    state.toggle_compact()
    assert state.is_compact is True

    state.toggle_compact()
    assert state.is_compact is False
