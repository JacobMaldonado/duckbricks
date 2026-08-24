"""Workspace page — shared file manager and code editor for SQL/Python assets."""

from __future__ import annotations

import asyncio
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from nicegui import ui

from app.config import MARIMO_URL, WORKSPACE_PATH
from app.services.git.folder_service import GitFolderService
from app.services.workspace import WorkspaceService
from app.services.workspace.workspace_service import WorkspaceNode
from app.ui.components.layout import layout_frame
from app.ui.workspace_layout import WORKSPACE_CODEMIRROR_LAYOUT_CSS, WORKSPACE_VIEWPORT_STYLE
from app.ui.workspace_utils import folder_name_from_url as _folder_name_from_url

_workspace_service = WorkspaceService(WORKSPACE_PATH)
_git_folder_service = GitFolderService(WORKSPACE_PATH)


_ICON_BY_EXTENSION = {
    ".sql": ("description", "blue-7"),
    ".py": ("code", "green-7"),
    ".ipynb": ("book", "orange-7"),
    ".md": ("article", "grey-7"),
    ".txt": ("text_snippet", "grey-6"),
}

_CODEMIRROR_LANGUAGE_BY_EXTENSION: dict[str, Any] = {
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
#     "duckbricks-utils",
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

_DRAG_DROP_JS = (
    """
<style>
.cm-editor .cm-tooltip-autocomplete { z-index: 9999 !important; }
.cm-editor { overflow: visible !important; }
"""
    + WORKSPACE_CODEMIRROR_LAYOUT_CSS
    + """
.ws-row-drop-target { outline: 2px dashed #1976d2 !important; background: #e3f2fd !important; }

/* File tree panel: normal vs collapsed */
.ws-file-tree-icon-strip {
    display: none;
    flex-direction: column;
    align-items: center;
    padding: 12px 4px;
    gap: 12px;
}
.ws-file-tree-body {
    display: flex;
    flex-direction: column;
    width: 100%;
}
body.ws-panel-collapsed .ws-file-tree-panel {
    width: 48px !important;
    min-width: 48px !important;
    overflow: visible !important;
    padding: 4px !important;
    position: relative !important;
}
body.ws-panel-collapsed .ws-file-tree-body { display: none !important; }
body.ws-panel-collapsed .ws-file-tree-icon-strip { display: flex !important; }
body.ws-panel-collapsed .ws-file-tree-panel:hover .ws-file-tree-body {
    display: flex !important;
    position: absolute;
    left: 0;
    top: 0;
    width: 280px;
    height: 100%;
    background: #f5f5f5;
    box-shadow: 4px 0 16px rgba(0,0,0,0.2);
    z-index: 500;
    overflow-y: auto;
    padding: 8px;
    flex-direction: column;
}

/* Editor vs iframe toggling */
body.ws-marimo-mode .ws-codemirror-panel { display: none !important; }
body.ws-marimo-mode .ws-marimo-iframe { display: flex !important; }
body.ws-marimo-mode .ws-save-btn { display: none !important; }
body.ws-marimo-mode .ws-edit-source-btn { display: inline-flex !important; }
.ws-marimo-iframe { display: none; border: none; width: 100%; flex: 1; min-height: 0; }
.ws-edit-source-btn { display: none !important; }

/* Collapse spacing inside folder expansions */
.ws-tree-row .nicegui-expansion-content {
    gap: 0 !important;
    padding: 0 !important;
}
</style>
<script>
document.addEventListener("dragover", function(e) {
    if (e.target.closest(".ws-tree-row")) { e.preventDefault(); }
});
</script>
"""
)


def workspace_page() -> None:
    """Render the Workspace page with a file tree and code editor panel."""
    layout_frame("Workspace")
    ui.add_head_html(_DRAG_DROP_JS)

    with ui.row().classes("w-full h-full gap-0").style(WORKSPACE_VIEWPORT_STYLE):
        _render_file_tree_panel()
        _render_editor_panel()


def _toggle_file_tree_panel(button: ui.button) -> None:
    storage = ui.context.client.storage
    collapsed = not storage.get("_ws_panel_collapsed", False)
    storage["_ws_panel_collapsed"] = collapsed
    button.set_icon("chevron_right" if collapsed else "chevron_left")
    ui.run_javascript(
        f"document.body.classList.toggle('ws-panel-collapsed', {'true' if collapsed else 'false'});"
    )


def _render_menu_item(icon: str, text: str, on_click) -> None:
    """Render a menu item with a leading Material icon and label."""
    with ui.menu_item(on_click=on_click, auto_close=True):
        with ui.item_section().props("avatar"):
            ui.icon(icon).classes("text-grey-7")
        with ui.item_section():
            ui.label(text).classes("text-body2")


def _render_file_tree_panel() -> None:
    with (
        ui.column()
        .classes("bg-grey-1 border-right ws-file-tree-panel")
        .style("width: 280px; min-width: 280px; overflow-y: auto; height: 100%; position: relative")
    ):
        with ui.element("div").classes("ws-file-tree-icon-strip"):
            ui.icon("folder_open", color="grey-7").classes("text-xl").tooltip("Workspace")

        with (
            ui.element("div")
            .classes("ws-file-tree-body q-pa-sm gap-1")
            .style("display: flex; flex-direction: column")
        ):
            tree_container: ui.column  # declared before use in lambdas below
            toggle_button: ui.button
            with ui.row().classes("w-full items-center justify-between q-mb-xs"):
                ui.label("Workspace").classes("text-weight-bold text-body2")
                with ui.row().classes("items-center").style("gap: 0"):
                    toggle_button = (
                        ui.button(
                            icon="chevron_left",
                            on_click=lambda: _toggle_file_tree_panel(toggle_button),
                        )
                        .props("flat dense size=xs color=grey-7")
                        .tooltip("Collapse/expand panel")
                    )
                    ui.button(icon="note_add", on_click=_open_new_file_dialog).props(
                        "flat dense size=xs"
                    ).tooltip("New file")
                    ui.button(icon="create_new_folder", on_click=_open_new_folder_dialog).props(
                        "flat dense size=xs color=amber-7"
                    ).tooltip("New folder")
                    with ui.button(icon="more_vert").props("flat dense size=xs color=grey-7"):
                        with ui.menu():
                            _render_menu_item("note_add", "New File", _open_new_file_dialog)
                            _render_menu_item(
                                "create_new_folder", "New Folder", _open_new_folder_dialog
                            )
                            ui.separator()
                            _render_menu_item(
                                "source",
                                "New Git Folder",
                                lambda: _open_new_git_folder_dialog(tree_container),
                            )

            tree_container = ui.column().classes("w-full gap-0")
            _refresh_tree(tree_container)
            ui.context.client.on_connect(lambda: _refresh_tree(tree_container))


def _refresh_tree(container: ui.column) -> None:
    container.clear()
    try:
        tracked = _git_folder_service.get_tracked_paths()
    except Exception:
        tracked = set()
    nodes = _workspace_service.list_tree(git_tracked_paths=tracked)
    with container:
        if not nodes:
            ui.label("No files yet.").classes("text-caption text-grey-5 q-pa-sm")
        else:
            for node in nodes:
                _render_tree_node(node, container)


def _render_tree_node(node: WorkspaceNode, tree_container: ui.column, depth: int = 0) -> None:
    indent = depth * 16
    if node.is_dir:
        folder_icon = "source" if node.is_git_folder else "folder"
        folder_color = "green-8" if node.is_git_folder else "amber-7"
        with (
            ui.expansion(node.name, icon=folder_icon)
            .classes("w-full text-body2 ws-tree-row")
            .style(f"padding-left: {indent}px")
            .props("dense draggable=true")
            .on("dragstart", lambda n=node: _on_dragstart(n.path))
            .on("dragover", lambda e: None)
            .on("drop", lambda n=node, c=tree_container: _on_drop(n.path, c, is_dir=True))
        ) as expansion:
            with expansion.add_slot("header"):
                with (
                    ui.row()
                    .classes("w-full items-center gap-1")
                    .style("min-width: 0; overflow: hidden")
                ):
                    ui.icon(folder_icon, color=folder_color).classes("text-sm flex-shrink-0")
                    ui.label(node.name).classes("text-body2 text-grey-9").style(
                        "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                        " flex: 1; min-width: 0"
                    ).tooltip(node.name)
                    if node.is_git_folder and node.git_branch:
                        ui.badge(node.git_branch, color="green-8").classes(
                            "cursor-pointer text-xs flex-shrink-0"
                        ).on(
                            "click.stop",
                            lambda n=node, c=tree_container: _open_git_dialog(n.path, c),
                        ).tooltip("Click to manage git repository")
                    ui.space()
                    _render_context_menu(node, tree_container)
            for child in node.children:
                _render_tree_node(child, tree_container, depth + 1)
    else:
        icon, color = _ICON_BY_EXTENSION.get(
            Path(node.name).suffix, ("insert_drive_file", "grey-6")
        )
        is_python = Path(node.name).suffix == ".py"
        is_notebook = Path(node.name).suffix == ".ipynb"
        with (
            ui.row()
            .classes(
                "w-full items-center gap-1 cursor-pointer"
                " hover:bg-blue-1 rounded q-px-sm q-py-xs ws-tree-row"
            )
            .style(
                f"padding-left: {indent + 8}px; min-width: 0; overflow: hidden; flex-wrap: nowrap"
            )
            .props("draggable=true")
            .on("click", lambda n=node: _open_file_in_editor(n.path))
            .on("dragstart", lambda n=node: _on_dragstart(n.path))
            .on("dragover", lambda e: None)
            .on("drop", lambda n=node, c=tree_container: _on_drop(n.path, c, is_dir=False))
        ):
            ui.icon(icon, color=color).classes("text-sm flex-shrink-0")
            ui.label(node.name).classes("text-body2 text-grey-9").style(
                "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0"
            ).tooltip(node.name)
            if is_python:
                marimo_file_url = f"{MARIMO_URL}/?file={urllib.parse.quote(node.path)}"
                ui.button(
                    icon="rocket_launch",
                    on_click=lambda url=marimo_file_url: ui.run_javascript(
                        f"window.open('{url}', '_blank')"
                    ),
                ).props("flat dense size=xs color=purple flex-shrink-0").tooltip("Open in Marimo")
            elif is_notebook:
                ui.icon("science", color="orange-6").classes("text-xs flex-shrink-0").tooltip(
                    "Jupyter notebook"
                )
            _render_context_menu(node, tree_container)


def _render_context_menu(node: WorkspaceNode, tree_container: ui.column) -> None:
    with ui.button(icon="more_vert").props("flat dense size=xs color=grey-7"):
        with ui.menu():
            if node.is_dir:
                ui.menu_item(
                    "New File",
                    on_click=lambda n=node: _open_new_file_dialog(n.path),
                    auto_close=True,
                )
                ui.menu_item(
                    "New Folder",
                    on_click=lambda n=node: _open_new_folder_dialog(n.path),
                    auto_close=True,
                )
                ui.separator()
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
            if node.is_dir and not node.is_git_folder:
                ui.separator()
                ui.menu_item(
                    "Convert to Git Folder",
                    on_click=lambda n=node, c=tree_container: _open_convert_to_git_dialog(n, c),
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
        .classes("flex-1 gap-2 ws-editor")
        .style("overflow: hidden; height: 100%; display: flex; flex-direction: column")
    ):
        with (
            ui.row()
            .classes("q-px-md q-pt-md w-full items-center justify-between")
            .style("flex-shrink: 0")
        ):
            current_file_label = ui.label("— no file open —").classes("text-caption text-grey-5")
            with ui.row().classes("gap-2"):
                ui.button("Save", icon="save", on_click=_save_current_file).props(
                    "flat color=primary"
                ).classes("ws-save-btn").tooltip("Save file")
                ui.button("Edit source", icon="edit", on_click=_deactivate_marimo_mode).props(
                    "flat color=grey-7"
                ).classes("ws-edit-source-btn").tooltip("Back to code editor")

        with ui.element("div").classes("w-full ws-codemirror-panel").style("padding: 0 16px 16px"):
            editor = ui.codemirror(
                value="",
                language=None,
                theme="githubLight",
            ).classes("w-full h-full")

        ui.element("iframe").classes("ws-marimo-iframe").style("padding: 0 16px 16px")

        ui.context.client.storage["_ws_current_path"] = ""
        ui.context.client.storage["_ws_editor"] = editor
        ui.context.client.storage["_ws_editor_id"] = editor.id
        ui.context.client.storage["_ws_label"] = current_file_label
        ui.context.client.storage["_ws_lang"] = None
        ui.context.client.storage["_ws_drag_source"] = ""


def _activate_marimo_mode(relative_path: str) -> None:
    marimo_file_url = f"{MARIMO_URL}/?file={urllib.parse.quote(relative_path)}"
    storage = ui.context.client.storage
    storage["_ws_current_path"] = relative_path

    label = cast(ui.label | None, storage.get("_ws_label"))
    if label:
        label.set_text(relative_path)

    ui.run_javascript(
        "document.body.classList.add('ws-marimo-mode');"
        f"var iframe = document.querySelector('.ws-marimo-iframe');"
        f"if (iframe) iframe.src = '{marimo_file_url}';"
    )


def _deactivate_marimo_mode() -> None:
    storage = ui.context.client.storage

    ui.run_javascript(
        "document.body.classList.remove('ws-marimo-mode');"
        "document.querySelector('.ws-marimo-iframe').src = '';"
    )

    relative_path: str = storage.get("_ws_current_path", "")
    if not relative_path:
        return

    extension = Path(relative_path).suffix.lower()
    language = _CODEMIRROR_LANGUAGE_BY_EXTENSION.get(extension)
    try:
        content = _workspace_service.read_file(relative_path)
    except FileNotFoundError:
        return

    editor = cast(ui.codemirror | None, storage.get("_ws_editor"))
    label = cast(ui.label | None, storage.get("_ws_label"))

    if editor:
        editor.set_language(language)
        editor.set_value(content)
        editor.update()

    if label:
        label.set_text(relative_path)


def _open_git_dialog(workspace_path: str, tree_container: ui.column) -> None:
    """Open the custom Git management dialog for the given workspace-relative path."""
    from app.ui.components.git_dialog import GitFolderDialog  # noqa: PLC0415

    GitFolderDialog(workspace_path, on_change=lambda: _refresh_tree(tree_container)).open()


def _open_file_in_editor(relative_path: str) -> None:
    extension = Path(relative_path).suffix.lower()

    if extension == ".py":
        _dispatch_python_file(relative_path)
        return

    if extension == ".ipynb":
        _dispatch_notebook_file(relative_path)
        return

    try:
        content = _workspace_service.read_file(relative_path)
    except FileNotFoundError:
        ui.notification(f"File not found: {relative_path}", type="warning")
        return

    _deactivate_marimo_mode()
    language = _CODEMIRROR_LANGUAGE_BY_EXTENSION.get(extension)

    storage = ui.context.client.storage
    storage["_ws_current_path"] = relative_path
    storage["_ws_lang"] = language

    editor = cast(ui.codemirror | None, storage.get("_ws_editor"))
    label = cast(ui.label | None, storage.get("_ws_label"))

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


def _dispatch_python_file(relative_path: str) -> None:
    """Ask how to open a .py file: in Marimo notebook mode or raw source editor."""
    try:
        content = _workspace_service.read_file(relative_path)
    except FileNotFoundError:
        ui.notification(f"File not found: {relative_path}", type="warning")
        return

    if "import marimo" in content:
        _activate_marimo_mode(relative_path)
        return

    with ui.dialog() as dialog, ui.card().style("min-width: 400px"):
        ui.label("Open Python file").classes("text-weight-bold text-body1")
        ui.label(
            "This file does not have a Marimo notebook structure. How do you want to open it?"
        ).classes("text-grey-7 text-caption q-mt-xs")
        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button(
                "Edit as source", on_click=lambda: _open_as_source(relative_path, dialog)
            ).props("flat color=grey-7")
            ui.button(
                "Open in Marimo",
                icon="rocket_launch",
                on_click=lambda: _convert_to_marimo_and_open(relative_path, content, dialog),
            ).props("color=purple")
    dialog.open()


def _open_as_source(relative_path: str, dialog: ui.dialog) -> None:
    dialog.close()
    try:
        content = _workspace_service.read_file(relative_path)
    except FileNotFoundError:
        ui.notification(f"File not found: {relative_path}", type="warning")
        return

    _deactivate_marimo_mode()
    language = _CODEMIRROR_LANGUAGE_BY_EXTENSION.get(Path(relative_path).suffix.lower())
    storage = ui.context.client.storage
    storage["_ws_current_path"] = relative_path
    storage["_ws_lang"] = language

    editor = cast(ui.codemirror | None, storage.get("_ws_editor"))
    label = cast(ui.label | None, storage.get("_ws_label"))
    if editor:
        editor.set_language(language)
        editor.set_value(content)
        editor.update()
    if label:
        label.set_text(relative_path)


def _convert_to_marimo_and_open(
    relative_path: str, original_content: str, dialog: ui.dialog
) -> None:
    dialog.close()
    new_content = _MARIMO_NOTEBOOK_TEMPLATE + original_content
    try:
        _workspace_service.write_file(relative_path, new_content)
    except Exception as exc:
        ui.notification(f"Could not update file: {exc}", type="negative")
        return
    ui.notification("Marimo notebook structure added.", type="positive")
    _activate_marimo_mode(relative_path)


def _dispatch_notebook_file(relative_path: str) -> None:
    """Ask whether to convert an .ipynb to a Marimo notebook or open it as raw JSON."""
    base_name = Path(relative_path).stem
    parent = str(Path(relative_path).parent)
    suggested_py = f"{parent}/{base_name}.py" if parent != "." else f"{base_name}.py"

    with ui.dialog() as dialog, ui.card().style("min-width: 440px"):
        ui.label("Jupyter Notebook").classes("text-weight-bold text-body1")
        ui.label(f"Convert '{Path(relative_path).name}' to a Marimo notebook?").classes(
            "text-grey-7 text-caption q-mt-xs"
        )
        ui.label(f"Output will be saved as: {suggested_py}").classes(
            "text-caption text-green-7 q-mb-xs"
        )
        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button(
                "Open as source",
                on_click=lambda: _open_notebook_as_source(relative_path, dialog),
            ).props("flat color=grey-7")
            ui.button(
                "Convert to Marimo",
                icon="transform",
                on_click=lambda: _run_marimo_convert(relative_path, suggested_py, dialog),
            ).props("color=orange-8")
    dialog.open()


def _open_notebook_as_source(relative_path: str, dialog: ui.dialog) -> None:
    dialog.close()
    try:
        content = _workspace_service.read_file(relative_path)
    except FileNotFoundError:
        ui.notification(f"File not found: {relative_path}", type="warning")
        return

    _deactivate_marimo_mode()
    storage = ui.context.client.storage
    storage["_ws_current_path"] = relative_path
    storage["_ws_lang"] = None

    editor = cast(ui.codemirror | None, storage.get("_ws_editor"))
    label = cast(ui.label | None, storage.get("_ws_label"))
    if editor:
        editor.set_language(None)
        editor.set_value(content)
        editor.update()
    if label:
        label.set_text(relative_path)


def _run_marimo_convert(relative_path: str, output_py_path: str, dialog: ui.dialog) -> None:
    """Run `marimo convert <notebook.ipynb> -o <output.py>` and open the result."""
    import subprocess  # noqa: PLC0415

    dialog.close()
    abs_input = Path(WORKSPACE_PATH) / relative_path
    abs_output = Path(WORKSPACE_PATH) / output_py_path

    try:
        result = subprocess.run(
            ["marimo", "convert", str(abs_input), "-o", str(abs_output)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Conversion failed")
    except Exception as exc:
        ui.notification(f"Conversion failed: {exc}", type="negative")
        return

    ui.notification(f"Converted to {output_py_path}", type="positive")
    _activate_marimo_mode(output_py_path)


def _save_current_file() -> None:
    storage = ui.context.client.storage
    relative_path: str = storage.get("_ws_current_path", "")
    editor = cast(ui.codemirror | None, storage.get("_ws_editor"))
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

            def _confirm_delete() -> None:
                _do_delete(node)
                dialog.close()
                _refresh_tree(tree_container)

            ui.button("Delete", on_click=_confirm_delete).props("color=negative")
    dialog.open()


def _do_delete(node: WorkspaceNode) -> None:
    try:
        _workspace_service.delete(node.path)
        ui.notification(f"Deleted: {node.name}", type="positive")
    except Exception as exc:
        ui.notification(f"Delete failed: {exc}", type="negative")


def _open_new_file_dialog(parent_path: str = "") -> None:
    title = f"New File in {Path(parent_path).name}" if parent_path else "New File"
    prefill = f"{parent_path}/" if parent_path else ""
    placeholder = f"{parent_path}/my_script.py" if parent_path else "queries/my_query.sql"
    with ui.dialog() as dialog, ui.card().style("min-width: 400px"):
        ui.label(title).classes("text-h6")
        path_input = ui.input(
            "File path (e.g. folder/my_query.sql)",
            placeholder=placeholder,
            value=prefill,
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


def _open_new_folder_dialog(parent_path: str = "") -> None:
    title = f"New Folder in {Path(parent_path).name}" if parent_path else "New Folder"
    prefill = f"{parent_path}/" if parent_path else ""
    placeholder = f"{parent_path}/sub_folder" if parent_path else "my_folder/sub"
    with ui.dialog() as dialog, ui.card().style("min-width: 400px"):
        ui.label(title).classes("text-h6")
        path_input = ui.input(
            "Folder path (e.g. my_folder/sub)",
            placeholder=placeholder,
            value=prefill,
        ).classes("w-full")
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


class _GitSourcePicker:
    """Connection + repository/URL + branch selection controls for git dialogs."""

    def __init__(self, connection_service) -> None:
        self._service = connection_service
        self._repos: list = []
        self.on_url_change: Callable[[str], None] | None = None

    def render(self) -> None:
        connections = self._service.list_all()
        connection_options = {str(c.id): f"{c.name} ({c.provider_type})" for c in connections}

        self.connection_select = ui.select(
            options=connection_options, label="Git Connection"
        ).classes("w-full")

        self.mode_switch = ui.switch("Choose from repositories", value=True).props("dense")

        with ui.column().classes("w-full gap-1") as self.browse_section:
            with ui.row().classes("w-full items-center gap-2"):
                self.repo_select = (
                    ui.select(options={}, label="Repository (browse & search)")
                    .classes("flex-1")
                    .props("use-input input-debounce=0 clearable")
                )
                self.repo_spinner = ui.spinner(size="sm")
                self.repo_spinner.set_visibility(False)
            self.branch_select = (
                ui.select(options={}, label="Branch")
                .classes("w-full")
                .props("use-input input-debounce=0 clearable")
            )

        with ui.column().classes("w-full gap-1") as self.url_section:
            self.url_input = (
                ui.input("Repository URL", placeholder="https://github.com/user/my-repo")
                .classes("w-full")
                .props("clearable")
            )
            self.branch_input = ui.input("Branch", value="main").classes("w-full")

        self.url_section.set_visibility(False)

        self.mode_switch.on_value_change(lambda _: self._sync_visibility())
        self.connection_select.on(
            "update:model-value", lambda _: asyncio.create_task(self._load_repos())
        )
        self.repo_select.on(
            "update:model-value", lambda e: asyncio.create_task(self._on_repo_change(e.args))
        )
        self.url_input.on("update:model-value", lambda e: self._notify_url_change(e.args or ""))

    def resolve(self) -> tuple[int | None, str, str]:
        """Return (connection_id, url, branch) from the current form state."""
        connection_id = int(self.connection_select.value) if self.connection_select.value else None
        if self.mode_switch.value:
            url = (self.repo_select.value or "").strip()
            branch = (self.branch_select.value or "main").strip() or "main"
        else:
            url = (self.url_input.value or "").strip()
            branch = (self.branch_input.value or "main").strip() or "main"
        return connection_id, url, branch

    def _sync_visibility(self) -> None:
        if self.mode_switch.value:
            self.browse_section.set_visibility(True)
            self.url_section.set_visibility(False)
            self.url_input.set_value("")
        else:
            self.browse_section.set_visibility(False)
            self.url_section.set_visibility(True)
            self.repo_select.set_value(None)

    async def _load_repos(self) -> None:
        if not self.connection_select.value:
            return
        self.repo_spinner.set_visibility(True)
        self.repo_select.disable()
        try:
            repos = await asyncio.to_thread(
                self._service.list_repositories, int(self.connection_select.value)
            )
            self._repos = repos
            self.repo_select.options = {r.clone_url: r.full_name for r in repos}
            self.repo_select.update()
        except Exception as exc:
            ui.notification(f"Could not load repositories: {exc}", type="negative")
        finally:
            self.repo_spinner.set_visibility(False)
            self.repo_select.enable()

    async def _load_branches(self, full_name: str, default_branch: str) -> None:
        if not full_name or not self.connection_select.value:
            return
        self.branch_select.disable()
        try:
            branches = await asyncio.to_thread(
                self._service.list_branches,
                int(self.connection_select.value),
                full_name,
            )
            self.branch_select.options = branches
            self.branch_select.update()
            if default_branch in branches:
                self.branch_select.set_value(default_branch)
            elif branches:
                self.branch_select.set_value(branches[0])
        except Exception as exc:
            ui.notification(f"Could not load branches: {exc}", type="negative")
        finally:
            self.branch_select.enable()

    async def _on_repo_change(self, repo_url: str) -> None:
        if not repo_url:
            return
        selected = next((r for r in self._repos if r.clone_url == repo_url), None)
        if selected:
            await self._load_branches(selected.full_name, selected.default_branch or "main")
        self._notify_url_change(repo_url)

    def _notify_url_change(self, url: str) -> None:
        if self.on_url_change:
            self.on_url_change(url)


def _open_convert_to_git_dialog(node: WorkspaceNode, tree_container: ui.column) -> None:
    from app.services.git.connection_service import GitConnectionService

    connection_service = GitConnectionService()

    with ui.dialog() as dialog, ui.card().style("min-width: 480px"):
        with ui.row().classes("items-center gap-2 q-mb-sm"):
            ui.icon("merge_type", color="green-8").classes("text-2xl")
            with ui.column().classes("gap-0"):
                ui.label(f'Convert "{node.name}" to Git Folder').classes(
                    "text-weight-bold text-body1"
                )
                ui.label(
                    "The remote repository must be empty (no commits). "
                    "All existing files will be pushed as the initial commit."
                ).classes("text-caption text-grey-7")

        connections = connection_service.list_all()
        if not connections:
            ui.label("No git connections configured.").classes("text-grey-6")
            ui.label("Add a connection in Settings first.").classes("text-caption text-grey-5")
            with ui.row().classes("justify-end q-mt-md"):
                ui.button("Go to Settings", on_click=lambda: ui.navigate.to("/settings")).props(
                    "color=primary"
                )
                ui.button("Cancel", on_click=dialog.close).props("flat")
            dialog.open()
            return

        picker = _GitSourcePicker(connection_service)
        picker.render()

        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            convert_btn = ui.button("Convert & Push", icon="upload").props("color=green-8")

        async def on_convert() -> None:
            connection_id, resolved_url, branch = picker.resolve()
            if not connection_id or not resolved_url:
                ui.notification("A connection and a repository are required.", type="warning")
                return
            convert_btn.props(add="loading")
            try:
                await asyncio.to_thread(
                    _git_folder_service.convert_to_git,
                    folder_path=node.path,
                    connection_id=connection_id,
                    repo_url=resolved_url,
                    branch=branch,
                )
                dialog.close()
                ui.notification(
                    f"'{node.path}' converted and pushed successfully.", type="positive"
                )
                _refresh_tree(tree_container)
            except Exception as exc:
                ui.notification(f"Conversion failed: {exc}", type="negative")
            finally:
                convert_btn.props(remove="loading")

        convert_btn.on_click(on_convert)
    dialog.open()


def _open_new_git_folder_dialog(tree_container: ui.column) -> None:
    from app.services.git.connection_service import GitConnectionService

    connection_service = GitConnectionService()

    with ui.dialog() as dialog, ui.card().style("min-width: 480px"):
        ui.label("New Git Folder").classes("text-h6")

        connections = connection_service.list_all()
        if not connections:
            ui.label("No git connections configured.").classes("text-grey-6")
            ui.label("Add a connection in Settings first.").classes("text-caption text-grey-5")
            with ui.row().classes("justify-end q-mt-md"):
                ui.button("Go to Settings", on_click=lambda: ui.navigate.to("/settings")).props(
                    "color=primary"
                )
                ui.button("Cancel", on_click=dialog.close).props("flat")
            dialog.open()
            return

        picker = _GitSourcePicker(connection_service)
        picker.render()

        folder_input = ui.input("Folder name in workspace", placeholder="my-repo").classes("w-full")
        picker.on_url_change = lambda url: folder_input.set_value(_folder_name_from_url(url))

        with ui.row().classes("justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            clone_btn = ui.button("Clone & Create").props("color=primary")

        async def on_clone() -> None:
            folder_name = folder_input.value.strip()
            connection_id, resolved_url, branch = picker.resolve()
            if not folder_name or not connection_id or not resolved_url:
                ui.notification("All fields are required.", type="warning")
                return
            clone_btn.props(add="loading")
            try:
                await asyncio.to_thread(
                    _git_folder_service.create,
                    folder_name=folder_name,
                    git_connection_id=connection_id,
                    repo_url=resolved_url,
                    branch=branch,
                )
                dialog.close()
                ui.notification(f"Git folder '{folder_name}' cloned successfully.", type="positive")
                _refresh_tree(tree_container)
            except Exception as exc:
                ui.notification(f"Clone failed: {exc}", type="negative")
            finally:
                clone_btn.props(remove="loading")

        clone_btn.on_click(on_clone)
    dialog.open()
