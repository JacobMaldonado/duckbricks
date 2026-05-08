"""Dialog shown when a git push/pull fails with an authentication error."""

from __future__ import annotations

import logging
from collections.abc import Callable

from nicegui import ui

from app.config import WORKSPACE_PATH
from app.services.git.connection_service import GitConnectionService
from app.services.git.folder_service import GitFolderService

_log = logging.getLogger(__name__)


class GitReconnectDialog:
    """Offers the user two recovery paths after an authentication failure:

    1. Switch to a different saved git connection.
    2. Update the PAT on the current connection.

    After a successful reconnection the ``on_reconnect`` callback is invoked so
    the caller can automatically retry the failed operation.
    """

    def __init__(self, workspace_path: str, on_reconnect: Callable[[], None]) -> None:
        self._workspace_path = workspace_path
        self._on_reconnect = on_reconnect
        self._connection_service = GitConnectionService()
        self._folder_service = GitFolderService(WORKSPACE_PATH)
        self._dialog: ui.dialog | None = None

    def open(self) -> None:
        """Build and display the reconnection dialog."""
        with ui.dialog() as dialog:
            self._dialog = dialog
            with ui.card().classes("q-pa-md").style("min-width: 420px; max-width: 520px"):
                self._render_header()
                with ui.tabs().classes("w-full") as tabs:
                    switch_tab = ui.tab("switch", label="Switch Connection", icon="swap_horiz")
                    token_tab = ui.tab("token", label="Update Token", icon="key")
                with ui.tab_panels(tabs, value=switch_tab).classes("w-full q-mt-sm"):
                    with ui.tab_panel(switch_tab):
                        self._render_switch_panel()
                    with ui.tab_panel(token_tab):
                        self._render_token_panel()
        dialog.open()

    def _render_header(self) -> None:
        with ui.row().classes("w-full items-center gap-2 q-mb-sm"):
            ui.icon("lock_reset", color="orange-8").classes("text-2xl")
            with ui.column().classes("gap-0"):
                ui.label("Authentication Failed").classes("text-weight-bold text-body1")
                ui.label(
                    "Your git credentials are no longer valid. "
                    "Switch to another connection or update your token."
                ).classes("text-caption text-grey-7")

    def _render_switch_panel(self) -> None:
        connections = self._connection_service.list_all()
        current_id = self._folder_service.get_connection_id(self._workspace_path)

        if not connections:
            ui.label("No saved connections found.").classes("text-grey-5 text-caption")
            return

        options = {c.id: f"{c.name} ({c.provider_type})" for c in connections}
        default = current_id if current_id in options else next(iter(options))
        connection_select = (
            ui.select(options, value=default, label="Git Connection")
            .classes("w-full")
            .props("outlined dense")
        )

        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=self._close).props("flat")
            ui.button(
                "Apply & Retry",
                icon="check",
                on_click=lambda: self._apply_switch(connection_select.value),
            ).props("color=primary")

    def _render_token_panel(self) -> None:
        token_input = (
            ui.input(label="Personal Access Token", password=True, password_toggle_button=True)
            .classes("w-full")
            .props("outlined dense")
        )

        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=self._close).props("flat")
            ui.button(
                "Save & Retry",
                icon="check",
                on_click=lambda: self._apply_token(token_input.value),
            ).props("color=primary")

    def _apply_switch(self, connection_id: int) -> None:
        if connection_id is None:
            ui.notification("Please select a connection.", type="warning")
            return
        try:
            self._folder_service.register_or_reassign(self._workspace_path, connection_id)
            self._close()
            self._on_reconnect()
        except Exception as exc:
            _log.exception("Failed to reassign connection: %s", exc)
            ui.notification(f"Could not switch connection: {exc}", type="negative")

    def _apply_token(self, new_token: str) -> None:
        token = new_token.strip()
        if not token:
            ui.notification("Token must not be empty.", type="warning")
            return
        connection_id = self._folder_service.get_connection_id(self._workspace_path)
        if connection_id is None:
            ui.notification("No connection found for this folder.", type="negative")
            return
        try:
            self._connection_service.update_token(connection_id, token)
            self._close()
            self._on_reconnect()
        except Exception as exc:
            _log.exception("Failed to update token: %s", exc)
            ui.notification(f"Could not update token: {exc}", type="negative")

    def _close(self) -> None:
        if self._dialog:
            self._dialog.close()
