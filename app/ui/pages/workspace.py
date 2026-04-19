"""Workspace page — shared file manager and code editor for SQL/Python assets."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from app.config import WORKSPACE_PATH
from app.services.workspace import WorkspaceService
from app.services.workspace.workspace_service import WorkspaceNode
from app.ui.components.layout import layout_frame

_workspace_service = WorkspaceService(WORKSPACE_PATH)

_ICON_BY_EXTENSION = {
    ".sql": ("description", "blue-7"),
    ".py": ("code", "green-7"),
    ".ipynb": ("book", "orange-7"),
    ".md": ("article", "grey-7"),
    ".txt": ("text_snippet", "grey-6"),
}


def workspace_page() -> None:
    """Render the Workspace page with a file tree and code editor panel."""
    layout_frame("Workspace")

    with ui.row().classes("w-full h-full gap-0").style("height: calc(100vh - 60px)"):
        _render_file_tree_panel()
        _render_editor_panel()


def _render_file_tree_panel() -> None:
    with (
        ui.column()
        .classes("bg-grey-1 border-right q-pa-sm gap-1")
        .style("width: 280px; min-width: 280px; overflow-y: auto; height: 100%")
    ):
        with ui.row().classes("w-full items-center justify-between q-mb-sm"):
            ui.label("Workspace").classes("text-weight-bold text-body2")
            with ui.row().classes("gap-1"):
                ui.button(icon="create_new_folder", on_click=_open_new_folder_dialog).props(
                    "flat dense size=sm"
                ).tooltip("New folder")
                ui.button(icon="note_add", on_click=_open_new_file_dialog).props(
                    "flat dense size=sm"
                ).tooltip("New file")

        tree_container = ui.column().classes("w-full gap-0")
        _refresh_tree(tree_container)
        ui.context.client.on_connect(lambda: _refresh_tree(tree_container))


def _refresh_tree(container: ui.column) -> None:
    container.clear()
    nodes = _workspace_service.list_tree()
    with container:
        if not nodes:
            ui.label("No files yet.").classes("text-caption text-grey-5 q-pa-sm")
        else:
            for node in nodes:
                _render_tree_node(node, container)


def _render_tree_node(node: WorkspaceNode, tree_container: ui.column, depth: int = 0) -> None:
    indent = depth * 16
    if node.is_dir:
        with (
            ui.expansion(node.name, icon="folder")
            .classes("w-full text-body2")
            .style(f"padding-left: {indent}px")
        ):
            for child in node.children:
                _render_tree_node(child, tree_container, depth + 1)
    else:
        icon, color = _ICON_BY_EXTENSION.get(
            Path(node.name).suffix, ("insert_drive_file", "grey-6")
        )
        with (
            ui.row()
            .classes(
                "w-full items-center gap-1 cursor-pointer hover:bg-blue-1 rounded q-px-sm q-py-xs"
            )
            .style(f"padding-left: {indent + 8}px")
            .on("click", lambda n=node: _open_file_in_editor(n.path))
        ):
            ui.icon(icon, color=color).classes("text-sm")
            ui.label(node.name).classes("text-body2 text-grey-9")
            ui.space()
            ui.button(
                icon="delete",
                on_click=lambda n=node, c=tree_container: _delete_item(n, c),
            ).props("flat dense size=xs color=negative").tooltip("Delete")


def _render_editor_panel() -> None:
    with ui.column().classes("flex-1 q-pa-md gap-2").style("overflow: hidden; height: 100%"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Editor").classes("text-weight-bold text-body2 text-grey-7")
            with ui.row().classes("gap-2"):
                ui.button("Save", icon="save", on_click=_save_current_file).props(
                    "flat color=primary"
                ).tooltip("Save file (Ctrl+S)")

        ui.context.client.storage["_ws_current_path"] = ""
        current_file_label = ui.label("— no file open —").classes("text-caption text-grey-5")
        editor = (
            ui.textarea()
            .classes("w-full font-mono")
            .style("flex: 1; height: calc(100vh - 180px); font-family: monospace; font-size: 13px")
            .props("outlined autogrow")
        )

        ui.context.client.storage["_ws_editor"] = editor
        ui.context.client.storage["_ws_label"] = current_file_label


def _open_file_in_editor(relative_path: str) -> None:
    try:
        content = _workspace_service.read_file(relative_path)
    except FileNotFoundError:
        ui.notification(f"File not found: {relative_path}", type="warning")
        return
    storage = ui.context.client.storage
    storage["_ws_current_path"] = relative_path
    editor: ui.textarea = storage.get("_ws_editor")
    label: ui.label = storage.get("_ws_label")
    if editor:
        editor.set_value(content)
    if label:
        label.set_text(relative_path)


def _save_current_file() -> None:
    storage = ui.context.client.storage
    relative_path: str = storage.get("_ws_current_path", "")
    editor: ui.textarea = storage.get("_ws_editor")
    if not relative_path:
        ui.notification("No file is currently open.", type="warning")
        return
    if not editor:
        return
    try:
        _workspace_service.write_file(relative_path, editor.value)
        ui.notification(f"Saved: {relative_path}", type="positive")
    except Exception as exc:
        ui.notification(f"Save failed: {exc}", type="negative")


def _open_new_file_dialog() -> None:
    with ui.dialog() as dialog, ui.card().style("min-width: 400px"):
        ui.label("New File").classes("text-h6")
        path_input = ui.input(
            "File path (e.g. folder/my_query.sql)",
            placeholder="queries/my_query.sql",
        ).classes("w-full")
        ui.label("Allowed extensions: .sql .py .ipynb .md .txt").classes("text-caption text-grey-6")

        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Create",
                on_click=lambda: _create_new_file(path_input.value, dialog),
            ).props("color=primary")
    dialog.open()


def _create_new_file(relative_path: str, dialog) -> None:
    relative_path = relative_path.strip()
    if not relative_path:
        ui.notification("Path is required.", type="warning")
        return
    try:
        _workspace_service.write_file(relative_path, "")
        dialog.close()
        ui.notification(f"Created: {relative_path}", type="positive")
        ui.navigate.to("/workspace")
    except Exception as exc:
        ui.notification(f"Error: {exc}", type="negative")


def _open_new_folder_dialog() -> None:
    with ui.dialog() as dialog, ui.card().style("min-width: 400px"):
        ui.label("New Folder").classes("text-h6")
        path_input = ui.input("Folder path (e.g. my_folder/sub)").classes("w-full")

        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Create",
                on_click=lambda: _create_folder(path_input.value, dialog),
            ).props("color=primary")
    dialog.open()


def _create_folder(relative_path: str, dialog) -> None:
    relative_path = relative_path.strip()
    if not relative_path:
        ui.notification("Path is required.", type="warning")
        return
    try:
        _workspace_service.create_folder(relative_path)
        dialog.close()
        ui.notification(f"Folder created: {relative_path}", type="positive")
        ui.navigate.to("/workspace")
    except Exception as exc:
        ui.notification(f"Error: {exc}", type="negative")


def _delete_item(node: WorkspaceNode, tree_container: ui.column) -> None:
    with ui.dialog() as dialog, ui.card():
        ui.label(f"Delete '{node.name}'?").classes("text-weight-bold")
        if node.is_dir:
            ui.label("This will delete the folder and all its contents.").classes("text-grey-7")
        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Delete",
                on_click=lambda: [
                    _do_delete(node),
                    dialog.close(),
                    _refresh_tree(tree_container),
                ],
            ).props("color=negative")
    dialog.open()


def _do_delete(node: WorkspaceNode) -> None:
    try:
        _workspace_service.delete(node.path)
        ui.notification(f"Deleted: {node.name}", type="positive")
    except Exception as exc:
        ui.notification(f"Delete failed: {exc}", type="negative")
