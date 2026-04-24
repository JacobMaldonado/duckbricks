"""Workspace page — shared file manager and code editor for SQL/Python assets."""

from __future__ import annotations

import time
import urllib.parse
from pathlib import Path

from nicegui import ui

from app.config import MARIMO_TOKEN_PASSWORD, MARIMO_URL, WORKSPACE_PATH
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

_CODEMIRROR_LANGUAGE_BY_EXTENSION: dict[str, str | None] = {
    ".sql": "SQL",
    ".py": "Python",
    ".ipynb": None,
    ".md": "Markdown",
    ".txt": None,
}

_MARIMO_NOTEBOOK_TEMPLATE = """\
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb",
#     "sqlglot",
# ]
# ///
import marimo

__generated_with = "0.10.0"
app = marimo.App()


if __name__ == "__main__":
    app.run()
"""

_DRAG_DROP_JS = """
<style>
.cm-editor .cm-tooltip-autocomplete { z-index: 9999 !important; }
.cm-editor { overflow: visible !important; }
.ws-editor .nicegui-codemirror { height: 100% !important; }
.ws-editor .cm-editor { height: 100% !important; }
.ws-editor .cm-scroller { overflow: auto !important; }
.ws-row-drop-target { outline: 2px dashed #1976d2 !important; background: #e3f2fd !important; }
</style>
<script>
document.addEventListener("dragover", function(e) {
    if (e.target.closest(".ws-tree-row")) { e.preventDefault(); }
});
</script>
"""


def workspace_page() -> None:
    """Render the Workspace page with a file tree and code editor panel."""
    layout_frame("Workspace")
    ui.add_head_html(_DRAG_DROP_JS)

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
                    "flat dense size=sm color=amber-7"
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
            .classes("w-full text-body2 ws-tree-row")
            .style(f"padding-left: {indent}px")
            .props("draggable=true")
            .on("dragstart", lambda n=node: _on_dragstart(n.path))
            .on("dragover", lambda e: None)
            .on("drop", lambda n=node, c=tree_container: _on_drop(n.path, c, is_dir=True))
        ) as expansion:
            with expansion.add_slot("header"):
                with ui.row().classes("w-full items-center gap-1"):
                    ui.icon("folder", color="amber-7").classes("text-sm")
                    ui.label(node.name).classes("text-body2 text-grey-9")
                    ui.space()
                    _render_context_menu(node, tree_container)
            for child in node.children:
                _render_tree_node(child, tree_container, depth + 1)
    else:
        icon, color = _ICON_BY_EXTENSION.get(
            Path(node.name).suffix, ("insert_drive_file", "grey-6")
        )
        is_python = Path(node.name).suffix == ".py"
        with (
            ui.row()
            .classes(
                "w-full items-center gap-1 cursor-pointer"
                " hover:bg-blue-1 rounded q-px-sm q-py-xs ws-tree-row"
            )
            .style(f"padding-left: {indent + 8}px")
            .props("draggable=true")
            .on("click", lambda n=node: _open_file_in_editor(n.path))
            .on("dragstart", lambda n=node: _on_dragstart(n.path))
            .on("dragover", lambda e: None)
            .on("drop", lambda n=node, c=tree_container: _on_drop(n.path, c, is_dir=False))
        ):
            ui.icon(icon, color=color).classes("text-sm")
            ui.label(node.name).classes("text-body2 text-grey-9")
            ui.space()
            if is_python:
                marimo_file_url = f"{MARIMO_URL}/?file={urllib.parse.quote(node.path)}&access_token={MARIMO_TOKEN_PASSWORD}"
                ui.button(
                    icon="rocket_launch",
                    on_click=lambda url=marimo_file_url: ui.run_javascript(
                        f"window.open('{url}', '_blank')"
                    ),
                ).props("flat dense size=xs color=purple").tooltip("Open in Marimo")
            _render_context_menu(node, tree_container)


def _render_context_menu(node: WorkspaceNode, tree_container: ui.column) -> None:
    with ui.button(icon="more_vert").props("flat dense size=xs color=grey-7"):
        with ui.menu():
            ui.menu_item(
                "Rename",
                on_click=lambda n=node, c=tree_container: _rename_dialog(n, c),
                auto_close=True,
            )
            ui.menu_item(
                "Clone",
                on_click=lambda n=node, c=tree_container: _clone_dialog(n, c),
                auto_close=True,
            )
            ui.separator()
            ui.menu_item(
                "Delete",
                on_click=lambda n=node, c=tree_container: _delete_dialog(n, c),
                auto_close=True,
            )


def _on_dragstart(source_path: str) -> None:
    ui.context.client.storage["_ws_drag_source"] = source_path


def _on_drop(dest_path: str, tree_container: ui.column, is_dir: bool) -> None:
    source_path = ui.context.client.storage.get("_ws_drag_source", "")
    if not source_path or source_path == dest_path:
        return
    dest_dir = dest_path if is_dir else str(Path(dest_path).parent)
    _move_dialog(source_path, dest_dir, tree_container)


def _render_editor_panel() -> None:
    with (
        ui.column()
        .classes("flex-1 q-pa-md gap-2 ws-editor")
        .style("overflow: hidden; height: 100%; display: flex; flex-direction: column")
    ):
        with ui.row().classes("w-full items-center justify-between").style("flex-shrink: 0"):
            current_file_label = ui.label("— no file open —").classes("text-caption text-grey-5")
            with ui.row().classes("gap-2"):
                ui.button("Save", icon="save", on_click=_save_current_file).props(
                    "flat color=primary"
                ).tooltip("Save file")

        editor = (
            ui.codemirror(
                value="",
                language=None,
                theme="githubLight",
            )
            .classes("w-full")
            .style("flex: 1; min-height: 0; overflow: visible")
        )

        ui.context.client.storage["_ws_current_path"] = ""
        ui.context.client.storage["_ws_editor"] = editor
        ui.context.client.storage["_ws_editor_id"] = editor.id
        ui.context.client.storage["_ws_label"] = current_file_label
        ui.context.client.storage["_ws_lang"] = None
        ui.context.client.storage["_ws_drag_source"] = ""


def _open_file_in_editor(relative_path: str) -> None:
    try:
        content = _workspace_service.read_file(relative_path)
    except FileNotFoundError:
        ui.notification(f"File not found: {relative_path}", type="warning")
        return

    extension = Path(relative_path).suffix.lower()
    language = _CODEMIRROR_LANGUAGE_BY_EXTENSION.get(extension)

    if extension == ".py" and "import marimo" not in content:
        content = _MARIMO_NOTEBOOK_TEMPLATE + content
        _workspace_service.write_file(relative_path, content)
        ui.notification("Marimo header added automatically.", type="info")

    storage = ui.context.client.storage
    storage["_ws_current_path"] = relative_path
    storage["_ws_lang"] = language

    editor: ui.codemirror = storage.get("_ws_editor")
    label: ui.label = storage.get("_ws_label")

    if editor:
        editor.set_language(language)
        editor.set_value(content)
        editor.update()

    if label:
        label.set_text(relative_path)

    if language == "SQL":
        editor_id = storage.get("_ws_editor_id")
        cache_bust = int(time.time())
        ui.run_javascript(
            f"import('/static/sql_completion.js?v={cache_bust}')"
            f".then(m => m.mount({editor_id}, {{}}))"
            f".catch(e => console.error('[sql_completion workspace]', e))"
        )


def _save_current_file() -> None:
    storage = ui.context.client.storage
    relative_path: str = storage.get("_ws_current_path", "")
    editor: ui.codemirror = storage.get("_ws_editor")
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


def _rename_dialog(node: WorkspaceNode, tree_container: ui.column) -> None:
    with ui.dialog() as dialog, ui.card().style("min-width: 400px"):
        ui.label("Rename").classes("text-h6")
        name_input = ui.input("New name", value=node.name).classes("w-full")
        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Rename",
                on_click=lambda: _do_rename(node, name_input.value, dialog, tree_container),
            ).props("color=primary")
    dialog.open()


def _do_rename(node: WorkspaceNode, new_name: str, dialog, tree_container: ui.column) -> None:
    new_name = new_name.strip()
    if not new_name or new_name == node.name:
        dialog.close()
        return
    try:
        _workspace_service.rename(node.path, new_name)
        dialog.close()
        ui.notification(f"Renamed to: {new_name}", type="positive")
        _refresh_tree(tree_container)
    except Exception as exc:
        ui.notification(f"Rename failed: {exc}", type="negative")


def _clone_dialog(node: WorkspaceNode, tree_container: ui.column) -> None:
    with ui.dialog() as dialog, ui.card().style("min-width: 380px"):
        ui.label(f"Clone '{node.name}'?").classes("text-weight-bold")
        ui.label("A copy will be created in the same folder.").classes("text-grey-7 text-caption")
        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Clone",
                on_click=lambda: _do_clone(node, dialog, tree_container),
            ).props("color=primary")
    dialog.open()


def _do_clone(node: WorkspaceNode, dialog, tree_container: ui.column) -> None:
    try:
        new_path = _workspace_service.clone(node.path)
        dialog.close()
        ui.notification(f"Cloned as: {Path(new_path).name}", type="positive")
        _refresh_tree(tree_container)
    except Exception as exc:
        ui.notification(f"Clone failed: {exc}", type="negative")


def _move_dialog(source_path: str, dest_dir: str, tree_container: ui.column) -> None:
    source_name = Path(source_path).name
    dest_label = dest_dir if dest_dir else "(workspace root)"
    with ui.dialog() as dialog, ui.card().style("min-width: 400px"):
        ui.label("Move file?").classes("text-weight-bold")
        ui.label(f"Move '{source_name}' into '{dest_label}'?").classes("text-grey-7")
        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Move",
                on_click=lambda: _do_move(source_path, dest_dir, dialog, tree_container),
            ).props("color=primary")
    dialog.open()


def _do_move(source_path: str, dest_dir: str, dialog, tree_container: ui.column) -> None:
    try:
        dest = dest_dir if dest_dir else "."
        _workspace_service.move(source_path, dest)
        dialog.close()
        ui.notification("Moved successfully.", type="positive")
        _refresh_tree(tree_container)
    except Exception as exc:
        ui.notification(f"Move failed: {exc}", type="negative")


def _delete_dialog(node: WorkspaceNode, tree_container: ui.column) -> None:
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
        initial_content = _MARIMO_NOTEBOOK_TEMPLATE if relative_path.endswith(".py") else ""
        _workspace_service.write_file(relative_path, initial_content)
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
