"""Large, read-only workspace file picker shared by job task editors."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from nicegui import ui

from app.services.workspace.workspace_service import WorkspaceNode, WorkspaceService

WORKSPACE_FILE_PICKER_CSS = """
<style>
.workspace-picker-body {
    display: grid;
    grid-template-columns: minmax(260px, 34%) minmax(0, 1fr);
    flex: 1;
    min-height: 0;
}
.workspace-picker-tree { min-height: 0; overflow-y: auto; border-right: 1px solid #e0e0e0; }
.workspace-picker-preview { min-height: 0; overflow: hidden; }
.workspace-picker-preview .nicegui-codemirror,
.workspace-picker-preview .cm-editor,
.workspace-picker-preview .cm-scroller { height: 100% !important; min-height: 0 !important; }
.workspace-picker-file.selected { background: #e3f2fd; color: #1565c0; }
@media (max-width: 760px) {
    .workspace-picker-body { display: flex; flex-direction: column; overflow-y: auto; }
    .workspace-picker-tree { min-height: 260px; border-right: 0; border-bottom: 1px solid #e0e0e0; }
    .workspace-picker-preview { min-height: 360px; }
}
</style>
"""


class WorkspaceFilePicker:
    """Selects a supported workspace file and previews its source without executing it."""

    _MAX_PREVIEW_CHARACTERS = 200_000
    _ICON_BY_EXTENSION = {".sql": ("description", "blue-7"), ".py": ("code", "green-7")}

    def __init__(
        self,
        workspace_service: WorkspaceService,
        on_select: Callable[[str], None],
        *,
        extensions: Sequence[str] = (".sql", ".py"),
        selected_path: str | None = None,
    ) -> None:
        self._workspace_service = workspace_service
        self._on_select = on_select
        self._extensions = {extension.lower() for extension in extensions}
        self._selected_path = selected_path
        self._tree_container: ui.column | None = None
        self._preview_editor: ui.codemirror | None = None
        self._preview_label: ui.label | None = None
        self._select_button: ui.button | None = None

    def open(self) -> None:
        ui.add_head_html(WORKSPACE_FILE_PICKER_CSS)
        with (
            ui.dialog().props("maximized") as dialog,
            ui.card().classes("w-full h-full q-pa-none gap-0"),
        ):
            with ui.row().classes("w-full items-center gap-3 q-pa-md border-b"):
                ui.icon("folder_open", color="primary", size="26px")
                ui.label("Choose workspace file").classes("text-h6 text-weight-medium")
                ui.space()
                search = (
                    ui.input(placeholder="Search files...")
                    .props("dense outlined clearable prepend-icon=search")
                    .style("width: 300px")
                )
                ui.button(icon="close", on_click=dialog.close).props(
                    "flat round dense color=grey-7 aria-label=Close"
                )

            with ui.element("div").classes("w-full workspace-picker-body"):
                with ui.column().classes("workspace-picker-tree gap-0 q-pa-sm"):
                    self._tree_container = ui.column().classes("w-full gap-0")
                with ui.column().classes("workspace-picker-preview gap-0"):
                    with ui.row().classes("w-full items-center q-px-md q-py-sm border-b"):
                        self._preview_label = ui.label("Select a file to preview").classes(
                            "text-caption text-grey-6 ellipsis"
                        )
                    self._preview_editor = (
                        ui.codemirror(value="", language=None, theme="githubLight")
                        .props("readonly")
                        .classes("w-full h-full")
                    )

            with ui.row().classes("w-full items-center gap-3 q-pa-md border-t"):
                selected_label = ui.label(self._selected_path or "No file selected").classes(
                    "text-caption text-grey-7 ellipsis"
                )
                ui.space()
                ui.button("Cancel", on_click=dialog.close).props("flat color=grey-7")

                def choose_file() -> None:
                    if not self._selected_path:
                        ui.notification("Select a workspace file first.", type="warning")
                        return
                    self._on_select(self._selected_path)
                    dialog.close()

                self._select_button = ui.button(
                    "Select file", icon="check", on_click=choose_file
                ).props("color=primary")

            def refresh(query: str = "") -> None:
                self._render_tree(query, selected_label)

            search.on_value_change(lambda event: refresh(event.value or ""))
            refresh()
            if self._selected_path:
                self._preview(self._selected_path, selected_label)
        dialog.open()

    def _render_tree(self, query: str, selected_label: ui.label) -> None:
        if not self._tree_container:
            return
        self._tree_container.clear()
        nodes = self._filter_nodes(self._workspace_service.list_tree(), query.strip().casefold())
        with self._tree_container:
            if not nodes:
                with ui.column().classes("w-full items-center q-pa-lg gap-1"):
                    ui.icon("search_off", color="grey-5", size="32px")
                    ui.label("No matching executable files").classes("text-grey-6")
                return
            for node in nodes:
                self._render_node(node, selected_label)

    def _render_node(self, node: WorkspaceNode, selected_label: ui.label, depth: int = 0) -> None:
        if node.is_dir:
            with ui.expansion(node.name, icon="folder").classes("w-full").props("dense"):
                for child in node.children:
                    self._render_node(child, selected_label, depth + 1)
            return
        extension = Path(node.name).suffix.lower()
        icon, color = self._ICON_BY_EXTENSION.get(extension, ("insert_drive_file", "grey-6"))
        selected = node.path == self._selected_path
        classes = (
            "w-full items-center gap-2 cursor-pointer rounded q-px-sm q-py-xs workspace-picker-file"
        )
        if selected:
            classes += " selected"
        with (
            ui.row()
            .classes(classes)
            .style(f"padding-left: {8 + depth * 12}px")
            .on("click", lambda path=node.path: self._preview(path, selected_label))
        ):
            ui.icon(icon, color=color, size="18px")
            ui.label(node.name).classes("text-body2 ellipsis")

    def _preview(self, relative_path: str, selected_label: ui.label) -> None:
        if not self._preview_editor or not self._preview_label:
            return
        try:
            content = self._workspace_service.read_file(relative_path)
        except (FileNotFoundError, UnicodeDecodeError, OSError) as exc:
            ui.notification(f"Could not preview file: {exc}", type="negative")
            return
        truncated = len(content) > self._MAX_PREVIEW_CHARACTERS
        visible_content = content[: self._MAX_PREVIEW_CHARACTERS]
        if truncated:
            visible_content += "\n\n-- Preview truncated --"
        language = "SQL" if Path(relative_path).suffix.lower() == ".sql" else "Python"
        self._preview_editor.set_language(language)  # type: ignore[arg-type]
        self._preview_editor.set_value(visible_content)
        self._preview_editor.update()
        self._selected_path = relative_path
        self._preview_label.set_text(relative_path)
        selected_label.set_text(relative_path)
        self._render_tree("", selected_label)

    def _filter_nodes(self, nodes: Sequence[WorkspaceNode], query: str) -> list[WorkspaceNode]:
        filtered: list[WorkspaceNode] = []
        for node in nodes:
            if node.is_dir:
                children = self._filter_nodes(node.children, query)
                if children:
                    filtered.append(
                        WorkspaceNode(
                            node.name,
                            node.path,
                            True,
                            children,
                            node.is_git_folder,
                            node.git_branch,
                        )
                    )
                continue
            if Path(node.name).suffix.lower() not in self._extensions:
                continue
            if not query or query in node.path.casefold():
                filtered.append(node)
        return filtered
