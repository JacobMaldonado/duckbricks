"""Settings page — application configuration including git provider connections."""

from __future__ import annotations

from nicegui import ui

from app.services.git.connection_service import GitConnectionService
from app.services.git.providers.factory import GitProviderFactory
from app.ui.components.layout import layout_frame

_connection_service = GitConnectionService()


def settings_page() -> None:
    """Render the Settings page with git connection management."""
    layout_frame("Settings")
    with ui.column().classes("w-full q-pa-lg gap-4"):
        ui.label("Settings").classes("text-h5 text-weight-bold")
        _render_git_connections_panel()


def _render_git_connections_panel() -> None:
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between q-mb-md"):
            ui.label("Git Connections").classes("text-h6")
            ui.button(
                icon="add",
                text="Add Connection",
                on_click=_open_add_connection_dialog,
            ).props("color=primary flat")

        connections_container = ui.column().classes("w-full gap-2")
        _refresh_connections(connections_container)
        ui.context.client.on_connect(lambda: _refresh_connections(connections_container))


def _refresh_connections(container: ui.column) -> None:
    container.clear()
    with container:
        connections = _connection_service.list_all()
        if not connections:
            ui.label("No git connections configured yet.").classes("text-grey-5 text-caption")
            return
        for connection in connections:
            _render_connection_card(connection, container)


def _render_connection_card(connection, container: ui.column) -> None:
    with ui.card().classes("w-full q-pa-sm").style("border: 1px solid #e0e0e0"):
        with ui.row().classes("w-full items-center gap-3"):
            ui.icon("hub", color="blue-7").classes("text-xl")
            with ui.column().classes("flex-1 gap-0"):
                ui.label(connection.name).classes("text-weight-medium")
                ui.label(connection.provider_type.capitalize()).classes("text-caption text-grey-6")

            status_badge = ui.badge("checking…", color="grey-5").classes("text-xs")

            ui.button(
                icon="check_circle",
                on_click=lambda c=connection, b=status_badge: _test_connection(c, b),
            ).props("flat dense size=sm color=green-7").tooltip("Test connection")

            ui.button(
                icon="delete",
                on_click=lambda c=connection, ct=container: _delete_connection(c, ct),
            ).props("flat dense size=sm color=negative").tooltip("Delete connection")

    ui.run_javascript(
        "setTimeout(() => {}, 0)"  # trigger status check on render via event
    )


def _test_connection(connection, badge: ui.badge) -> None:
    try:
        valid = _connection_service.test_connection(connection.id)
        if valid:
            badge.props("color=green-7")
            badge.set_text("valid")
            badge.update()
            ui.notification(f"Connection '{connection.name}' is valid.", type="positive")
        else:
            badge.props("color=orange-7")
            badge.set_text("expired / invalid")
            badge.update()
            ui.notification(
                f"Connection '{connection.name}' is expired or invalid. "
                "Please review the token.",
                type="warning",
            )
    except Exception as exc:
        badge.props("color=negative")
        badge.set_text("error")
        badge.update()
        ui.notification(f"Test failed: {exc}", type="negative")


def _delete_connection(connection, container: ui.column) -> None:
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Delete '{connection.name}'?").classes("text-weight-bold")
        ui.label(
            "All git folders linked to this connection will also be removed from tracking."
        ).classes("text-grey-7 text-caption")
        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            def confirm() -> None:
                try:
                    _connection_service.delete(connection.id)
                    dialog.close()
                    ui.notification(f"Deleted '{connection.name}'.", type="positive")
                    _refresh_connections(container)
                except Exception as exc:
                    ui.notification(f"Delete failed: {exc}", type="negative")

            ui.button("Delete", on_click=confirm).props("color=negative")
    dialog.open()


def _open_add_connection_dialog() -> None:
    supported = GitProviderFactory.supported_types()
    provider_options = {p: p.capitalize() for p in supported}

    with ui.dialog() as dialog, ui.card().style("min-width: 440px"):
        ui.label("Add Git Connection").classes("text-h6")

        name_input = ui.input("Connection name", placeholder="My GitHub Account").classes("w-full")
        provider_select = ui.select(
            options=provider_options,
            label="Provider",
            value=supported[0] if supported else None,
        ).classes("w-full")
        token_input = ui.input(
            "Personal Access Token", password=True, password_toggle_button=True
        ).classes("w-full")
        ui.label(
            "The token is encrypted before being stored. It is never saved in plaintext."
        ).classes("text-caption text-grey-6")

        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Test & Save",
                on_click=lambda: _save_connection(
                    name_input.value,
                    provider_select.value,
                    token_input.value,
                    dialog,
                ),
            ).props("color=primary")
    dialog.open()


def _save_connection(name: str, provider_type: str, token: str, dialog) -> None:
    name = name.strip()
    token = token.strip()
    if not name or not token:
        ui.notification("Name and token are required.", type="warning")
        return
    try:
        connection = _connection_service.create(name=name, provider_type=provider_type, token=token)
        provider = _connection_service.build_provider(connection)
        if not provider.validate():
            _connection_service.delete(connection.id)
            ui.notification(
                "Token is invalid or expired. Connection was not saved.",
                type="negative",
            )
            return
        dialog.close()
        ui.notification(f"Connection '{name}' saved successfully.", type="positive")
        ui.navigate.to("/settings")
    except Exception as exc:
        ui.notification(f"Could not save connection: {exc}", type="negative")
