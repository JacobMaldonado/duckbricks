"""Git Folder management dialog — branch switching, pull, commit, diff, discard."""

from __future__ import annotations

import logging

from nicegui import ui

from app.services.git.models import ChangedFile, GitStatus
from app.services.git.operations_service import GitOperationsService

_log = logging.getLogger(__name__)

_GIT_DIALOG_CSS = """
<style>
.git-dialog-container { display: flex; flex-direction: column; height: 70vh; min-height: 400px; }
.git-files-panel { flex: 0 0 40%; border-right: 1px solid #e0e0e0; overflow-y: auto; }
.git-diff-panel { flex: 1; overflow: hidden; background: #fafafa; }
.git-file-row { cursor: pointer; border-radius: 4px; padding: 4px 8px; }
.git-file-row:hover { background: #e3f2fd; }
.git-file-row.selected { background: #bbdefb; }
.git-diff-panel .nicegui-codemirror { height: 100% !important; }
.git-diff-panel .cm-editor { height: 100% !important; }
.git-diff-panel .cm-scroller { overflow: auto !important; }
.git-diff-panel .cm-line.diff-line-added { background-color: #d1fae5 !important; }
.git-diff-panel .cm-line.diff-line-removed { background-color: #fee2e2 !important; }
.git-diff-panel .cm-line.diff-line-hunk { background-color: #dbeafe !important; }
</style>
"""

_GIT_DIFF_LINE_STYLER_JS = """
(function() {
    if (window._gitDiffLineObserver) {
        window._gitDiffLineObserver.disconnect();
        window._gitDiffLineObserver = null;
    }

    function classifyLine(line) {
        const text = line.textContent || '';
        line.classList.remove('diff-line-added', 'diff-line-removed', 'diff-line-hunk');
        if (text.startsWith('+')) line.classList.add('diff-line-added');
        else if (text.startsWith('-')) line.classList.add('diff-line-removed');
        else if (text.startsWith('@@')) line.classList.add('diff-line-hunk');
    }

    function styleAllLines(root) {
        root.querySelectorAll('.cm-line').forEach(classifyLine);
    }

    const panel = document.querySelector('.git-diff-panel');
    if (!panel) return;

    window._gitDiffLineObserver = new MutationObserver(() => styleAllLines(panel));
    window._gitDiffLineObserver.observe(panel, { childList: true, subtree: true });
    styleAllLines(panel);
})();
"""


class GitFolderDialog:
    """Full-screen dialog for managing a git folder — branch, pull, commit, diff, discard."""

    def __init__(self, workspace_path: str) -> None:
        self._workspace_path = workspace_path
        self._service = GitOperationsService()
        self._status: GitStatus | None = None
        self._selected_files: set[str] = set()
        self._active_diff_path: str | None = None

        self._dialog: ui.dialog | None = None
        self._files_container: ui.column | None = None
        self._diff_panel: ui.element | None = None
        self._branch_select: ui.select | None = None
        self._commit_input: ui.textarea | None = None

    def open(self) -> None:
        """Build and open the dialog."""
        ui.add_head_html(_GIT_DIALOG_CSS)
        with ui.dialog().props("maximized persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-full h-full q-pa-none").style("overflow: hidden"):
                self._render_header()
                with (
                    ui.row()
                    .classes("w-full gap-0")
                    .style("flex: 1; min-height: 0; overflow: hidden")
                ):
                    with ui.column().classes("git-files-panel q-pa-sm").style("width: 40%"):
                        self._files_container = ui.column().classes("w-full gap-1")
                        self._render_commit_footer()
                    with ui.element("div").classes("git-diff-panel q-pa-sm").style("flex: 1"):
                        self._diff_panel = ui.element("div").classes(
                            "w-full h-full relative-position"
                        )
                        with self._diff_panel:
                            ui.label("← Select a file to view its diff").classes(
                                "absolute-center text-grey-5 text-body2"
                            )
        dialog.open()
        ui.run_javascript(_GIT_DIFF_LINE_STYLER_JS)
        self._reload()

    def _render_header(self) -> None:
        with (
            ui.row()
            .classes("w-full items-center q-px-md q-py-sm bg-grey-2 gap-2")
            .style("flex-shrink: 0")
        ):
            ui.label(f"Git — {self._workspace_path}").classes("text-weight-bold text-body1")
            ui.space()

            self._branch_select = (
                ui.select(
                    options=[],
                    label="Branch",
                    on_change=self._on_branch_change,
                )
                .props("dense outlined")
                .style("min-width: 180px")
            )

            ui.button(
                icon="add",
                on_click=self._open_new_branch_dialog,
            ).props("flat dense").tooltip("Create new branch")

            ui.button(
                "Pull",
                icon="download",
                on_click=self._pull,
            ).props("flat color=primary dense").tooltip("Pull from remote")

            ui.button(icon="close", on_click=self._close).props("flat dense color=grey-7")

    def _render_commit_footer(self) -> None:
        with ui.column().classes("w-full q-mt-sm gap-1"):
            ui.separator()
            self._commit_input = (
                ui.textarea(
                    label="Commit message",
                    placeholder="Describe your changes…",
                )
                .classes("w-full")
                .props("outlined dense rows=2")
            )
            ui.button(
                "Commit & Push",
                icon="cloud_upload",
                on_click=self._commit_and_push,
            ).props("color=primary").classes("w-full")

    def _reload(self) -> None:
        try:
            self._status = self._service.get_status(self._workspace_path)
        except Exception as exc:
            ui.notification(f"Error reading repository: {exc}", type="negative")
            return

        self._refresh_branch_selector()
        self._refresh_files()

    def _refresh_branch_selector(self) -> None:
        if self._status is None or self._branch_select is None:
            return
        try:
            branches = self._service.list_branches(self._workspace_path)
        except Exception:
            branches = [self._status.branch]

        self._branch_select.options = branches
        self._branch_select.set_value(self._status.branch)
        self._branch_select.update()

    def _refresh_files(self) -> None:
        if self._files_container is None or self._status is None:
            return
        self._files_container.clear()
        with self._files_container:
            if not self._status.changed_files:
                ui.label("No changes — working tree clean.").classes(
                    "text-caption text-grey-5 q-pa-sm"
                )
                return
            staged = [f for f in self._status.changed_files if f.is_staged]
            unstaged = [f for f in self._status.changed_files if not f.is_staged]
            if staged:
                ui.label("Staged").classes("text-caption text-grey-6 q-mt-xs")
                for f in staged:
                    self._render_file_row(f)
            if unstaged:
                ui.label("Changes").classes("text-caption text-grey-6 q-mt-xs")
                for f in unstaged:
                    self._render_file_row(f)

    def _render_file_row(self, changed_file: ChangedFile) -> None:
        is_selected = changed_file.path in self._selected_files
        row_classes = "git-file-row w-full items-center gap-2"
        if self._active_diff_path == changed_file.path:
            row_classes += " selected"

        with (
            ui.row()
            .classes(row_classes)
            .on("click", lambda f=changed_file: self._show_diff(f.path))
        ):
            ui.checkbox(
                value=is_selected,
                on_change=lambda e, p=changed_file.path: self._toggle_file(p, e.value),
            ).props("dense")

            ui.badge(
                changed_file.status_label,
                color=changed_file.status_color,
            ).classes("text-xs")

            ui.label(changed_file.path).classes("text-body2 text-grey-9").style(
                "flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap"
            )

            if changed_file.status != "deleted":
                ui.button(
                    icon="undo",
                    on_click=lambda f=changed_file: self._discard_file(f),
                ).props("flat dense size=xs color=orange-8").tooltip("Discard changes")

    def _toggle_file(self, path: str, checked: bool) -> None:
        if checked:
            self._selected_files.add(path)
        else:
            self._selected_files.discard(path)

    def _show_diff(self, file_path: str) -> None:
        self._active_diff_path = file_path
        if self._diff_panel is None:
            return
        try:
            diff_text = self._service.get_diff(self._workspace_path, file_path)
        except Exception as exc:
            diff_text = f"(error loading diff: {exc})"
        self._diff_panel.clear()
        with self._diff_panel:
            (
                ui.codemirror(value=diff_text, language="diff", theme="githubLight")
                .classes("w-full h-full")
                .disable()
            )
        self._refresh_files()

    def _on_branch_change(self, event: object) -> None:
        if self._status is None:
            return
        selected: str = getattr(event, "value", None) or ""
        if not selected or selected == self._status.branch:
            return
        try:
            self._service.checkout_branch(self._workspace_path, selected)
            ui.notification(f"Switched to branch '{selected}'", type="positive")
            self._reload()
        except Exception as exc:
            ui.notification(f"Branch switch failed: {exc}", type="negative")

    def _open_new_branch_dialog(self) -> None:
        with ui.dialog() as inner:
            with ui.card().classes("q-pa-md").style("min-width: 320px"):
                ui.label("Create new branch").classes("text-weight-bold")
                name_input = ui.input(label="Branch name").classes("w-full")
                with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
                    ui.button("Cancel", on_click=inner.close).props("flat")
                    ui.button(
                        "Create",
                        on_click=lambda: self._create_branch(name_input.value, inner),
                    ).props("color=primary")
        inner.open()

    def _create_branch(self, name: str, dialog: ui.dialog) -> None:
        name = name.strip()
        if not name:
            ui.notification("Branch name is required.", type="warning")
            return
        try:
            self._service.checkout_branch(self._workspace_path, name, create=True)
            ui.notification(f"Created and switched to '{name}'", type="positive")
            dialog.close()
            self._reload()
        except Exception as exc:
            ui.notification(f"Failed to create branch: {exc}", type="negative")

    def _discard_file(self, changed_file: ChangedFile) -> None:
        try:
            self._service.discard_file(self._workspace_path, changed_file.path)
            ui.notification(f"Discarded changes in '{changed_file.path}'", type="positive")
            self._selected_files.discard(changed_file.path)
            if self._active_diff_path == changed_file.path:
                self._active_diff_path = None
                if self._diff_panel:
                    self._diff_panel.clear()
                    with self._diff_panel:
                        ui.label("← Select a file to view its diff").classes(
                            "absolute-center text-grey-5 text-body2"
                        )
            self._reload()
        except Exception as exc:
            ui.notification(f"Discard failed: {exc}", type="negative")

    def _pull(self) -> None:
        try:
            self._service.pull(self._workspace_path)
            ui.notification("Pull successful.", type="positive")
            self._reload()
        except Exception as exc:
            ui.notification(f"Pull failed: {exc}", type="negative")

    def _commit_and_push(self) -> None:
        if not self._selected_files:
            ui.notification("Select at least one file to commit.", type="warning")
            return
        message = (self._commit_input.value or "").strip() if self._commit_input else ""
        if not message:
            ui.notification("Please enter a commit message.", type="warning")
            return
        try:
            self._service.commit_and_push(
                self._workspace_path,
                message,
                list(self._selected_files),
            )
            ui.notification("Committed and pushed successfully.", type="positive")
            self._selected_files.clear()
            if self._commit_input:
                self._commit_input.set_value("")
            self._reload()
        except Exception as exc:
            ui.notification(f"Commit/push failed: {exc}", type="negative")

    def _close(self) -> None:
        if self._dialog:
            self._dialog.close()
