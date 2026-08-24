"""Shared application navigation drawer."""

from __future__ import annotations

import json
from dataclasses import dataclass

from nicegui import ui


@dataclass(frozen=True)
class NavigationDestination:
    """A route rendered in the application navigation drawer."""

    route: str
    label: str
    icon: str
    starts_group: bool = False

    def is_active(self, current_path: str) -> bool:
        normalized_path = current_path.rstrip("/") or "/"
        return normalized_path == self.route or normalized_path.startswith(f"{self.route}/")

    def item_classes(self, current_path: str) -> str:
        classes = "w-full"
        if self.is_active(current_path):
            classes += " bg-blue-1 text-primary"
        return classes

    def icon_classes(self, current_path: str) -> str:
        return "text-primary" if self.is_active(current_path) else "text-grey-7"

    def label_classes(self, current_path: str) -> str:
        if self.is_active(current_path):
            return "text-primary text-body2 text-weight-medium"
        return "text-grey-9 text-body2"


class NavigationDrawerState:
    """Tracks the persistent drawer mode and temporary hover expansion."""

    def __init__(self) -> None:
        self._compact = False
        self._pointer_inside = False

    @property
    def is_compact(self) -> bool:
        return self._compact

    @property
    def should_render_mini(self) -> bool:
        return self._compact and not self._pointer_inside

    def set_compact(self, compact: bool) -> None:
        self._compact = compact

    def toggle_compact(self) -> None:
        self._compact = not self._compact

    def pointer_entered(self) -> None:
        self._pointer_inside = True

    def pointer_left(self) -> None:
        self._pointer_inside = False


NAVIGATION_DESTINATIONS = (
    NavigationDestination(route="/explorer", label="Metastore Explorer", icon="storage"),
    NavigationDestination(route="/query", label="Query Editor", icon="code"),
    NavigationDestination(route="/jobs", label="Jobs", icon="schedule"),
    NavigationDestination(route="/workspace", label="Workspace", icon="folder_open"),
    NavigationDestination(
        route="/settings",
        label="Settings",
        icon="settings",
        starts_group=True,
    ),
)


class NavigationDrawer:
    """Renders and controls the shared expanded or hover-expandable drawer."""

    _COMPACT_PREFERENCE_KEY = "duckbricks.navigation.compact"

    def __init__(self, current_path: str) -> None:
        self._current_path = current_path
        self._state = NavigationDrawerState()
        self._drawer: ui.left_drawer | None = None
        self._toggle_icon: ui.icon | None = None
        self._toggle_label: ui.label | None = None

    def render(self) -> None:
        with (
            ui.left_drawer(value=True, bordered=True)
            .classes("bg-grey-1 p-0")
            .props("width=200 mini-width=56") as drawer
        ):
            self._drawer = drawer
            with ui.column().classes("w-full h-full no-wrap gap-0"):
                with ui.list().props("padding").classes("w-full q-pt-sm"):
                    for destination in NAVIGATION_DESTINATIONS:
                        if destination.starts_group:
                            ui.separator().classes("q-my-xs")
                        self._render_destination(destination)

                ui.space()
                ui.separator()
                self._render_mode_toggle()

        drawer.on("mouseenter", self._handle_pointer_entered)
        drawer.on("mouseleave", self._handle_pointer_left)
        ui.context.client.on_connect(self._restore_compact_preference)

    def toggle_visibility(self) -> None:
        if self._drawer is not None:
            self._drawer.toggle()

    def _render_destination(self, destination: NavigationDestination) -> None:
        active = destination.is_active(self._current_path)
        with (
            ui.item(on_click=lambda route=destination.route: ui.navigate.to(route))
            .props("clickable v-ripple")
            .classes(destination.item_classes(self._current_path)) as item
        ):
            with ui.item_section().props("avatar"):
                ui.icon(destination.icon).classes(destination.icon_classes(self._current_path))
            with ui.item_section():
                ui.label(destination.label).classes(destination.label_classes(self._current_path))

        if active:
            item.props("active aria-current=page")
        item.tooltip(destination.label)

    def _render_mode_toggle(self) -> None:
        with (
            ui.item(on_click=self._toggle_compact_mode)
            .props('clickable v-ripple aria-label="Toggle navigation size"')
            .classes("w-full") as item
        ):
            with ui.item_section().props("avatar"):
                self._toggle_icon = ui.icon("chevron_left").classes("text-grey-7")
            with ui.item_section().classes("q-mini-drawer-hide"):
                self._toggle_label = ui.label("Icons only").classes("text-grey-9 text-body2")

        item.tooltip("Toggle icons-only navigation")

    def _toggle_compact_mode(self) -> None:
        self._state.toggle_compact()
        self._apply_mode()
        compact_value = json.dumps(str(self._state.is_compact).lower())
        preference_key = json.dumps(self._COMPACT_PREFERENCE_KEY)
        ui.run_javascript(f"localStorage.setItem({preference_key}, {compact_value})")

    def _handle_pointer_entered(self) -> None:
        self._state.pointer_entered()
        self._apply_mode()

    def _handle_pointer_left(self) -> None:
        self._state.pointer_left()
        self._apply_mode()

    async def _restore_compact_preference(self) -> None:
        preference_key = json.dumps(self._COMPACT_PREFERENCE_KEY)
        compact = await ui.run_javascript(f"localStorage.getItem({preference_key}) === 'true'")
        self._state.set_compact(bool(compact))
        self._apply_mode()

    def _apply_mode(self) -> None:
        if self._drawer is None:
            return

        if self._state.should_render_mini:
            self._drawer.props(add="mini")
        else:
            self._drawer.props(remove="mini")

        if self._toggle_icon is not None:
            self._toggle_icon.set_name(
                "chevron_right" if self._state.is_compact else "chevron_left"
            )
        if self._toggle_label is not None:
            self._toggle_label.set_text("Show names" if self._state.is_compact else "Icons only")
