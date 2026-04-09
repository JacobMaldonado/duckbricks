"""Catalog browser component — hierarchical DuckLake catalog tree."""

from collections.abc import Callable

from nicegui import ui

from app.services.metastore.ducklake_manager import MetastoreManager

_LOADING_ID_PREFIX = "__loading_"


def _make_loading_child(parent_id: str) -> dict:
    return {
        "id": f"{_LOADING_ID_PREFIX}{parent_id}",
        "label": "Loading...",
        "icon": "hourglass_empty",
    }


class CatalogBrowser:
    """Renders and manages the hierarchical catalog tree with search and actions."""

    def __init__(
        self,
        container: ui.element,
        on_table_select: Callable[[str], None] | None = None,
        on_insert_to_editor: Callable[[str], None] | None = None,
        metastore: MetastoreManager | None = None,
    ) -> None:
        self._container = container
        self._on_table_select = on_table_select
        self._on_insert_to_editor = on_insert_to_editor
        self._metastore = metastore or _default_manager()
        self._loaded: set[str] = set()
        self._tree: ui.tree | None = None
        self._tree_container: ui.column | None = None
        self._search_results_container: ui.column | None = None
        self._search_value: str = ""
        self._context_menu_dialog: ui.dialog | None = None
        self._context_menu_label: ui.label | None = None
        self._context_menu_path: str = ""
        self._render()

    def _render(self) -> None:
        with self._container:
            search_input = (
                ui.input(placeholder="Search tables...")
                .classes("w-full q-px-sm q-pt-sm")
                .props("dense clearable")
            )
            self._tree_container = ui.column().classes("w-full")
            self._search_results_container = ui.column().classes("w-full")
            self._search_results_container.set_visibility(False)

        search_input.on_value_change(self._on_search_change)

        initial_nodes = self._load_catalog_nodes()
        with self._tree_container:
            self._tree = ui.tree(
                initial_nodes,
                node_key="id",
                label_key="label",
                on_select=self._handle_select,
                on_expand=self._handle_expand,
            ).classes("w-full")

        self._tree.add_slot(
            "default-header",
            r"""
            <div class="row items-center full-width no-wrap"
                 style="cursor: pointer"
                 :draggable="props.node.draggable"
                 @dragstart="$event.dataTransfer.setData('text/plain', props.node.id)"
                 @click="props.node.children !== undefined
                   ? props.tree.setExpanded(props.key, !props.expanded) : null">
              <q-icon v-if="props.node.icon" :name="props.node.icon"
                      class="q-mr-xs text-grey-7" size="18px"/>
              <span class="col text-body2 text-grey-9 ellipsis">{{ props.node.label }}</span>
              <q-btn v-if="props.node.insertable" flat dense round
                     icon="keyboard_double_arrow_right"
                     size="10px" class="text-grey-5 q-ml-xs"
                     @click.stop="$emit('insert', props.node.id)"/>
              <q-btn flat dense round icon="more_vert" size="10px"
                     class="text-grey-5"
                     @click.stop="$emit('menu', props.node.id)"/>
            </div>
            """,
        )
        self._tree.on(
            "insert",
            lambda e: self._handle_insert(e.args[0] if isinstance(e.args, list) else e.args),
        )
        self._tree.on(
            "menu",
            lambda e: self._handle_menu(e.args[0] if isinstance(e.args, list) else e.args),
        )
        self._context_menu_dialog = self._build_context_menu()

    def _load_catalog_nodes(self) -> list[dict]:
        if not self._metastore.is_initialized:
            return [{"id": "__not_initialized__", "label": "⚠️ Not initialized", "icon": "warning"}]
        try:
            catalogs = self._metastore.list_catalogs()
            if not catalogs:
                return [{"id": "__no_catalogs__", "label": "(No catalogs)", "icon": "info"}]
            return [
                {"id": cat, "label": cat, "icon": "storage", "children": [_make_loading_child(cat)]}
                for cat in catalogs
            ]
        except Exception as exc:
            return [{"id": "__error__", "label": f"Error: {exc}", "icon": "error"}]

    def _handle_expand(self, e) -> None:
        expanded_keys: list = e.value if isinstance(e.value, list) else [e.value]
        changed = False
        for key in expanded_keys:
            if key in self._loaded or key.startswith("__"):
                continue
            node = _find_node(self._tree._props["nodes"], key)
            if node is None:
                continue
            children = node.get("children", [])
            if children and not children[0]["id"].startswith(_LOADING_ID_PREFIX):
                self._loaded.add(key)
                continue
            parts = key.split(".")
            try:
                if len(parts) == 1:
                    schemas = self._metastore.list_schemas(parts[0])
                    node["children"] = (
                        [{"id": f"{key}.__empty__", "label": "(No schemas)", "icon": "info"}]
                        if not schemas
                        else [
                            {
                                "id": f"{key}.{s}",
                                "label": s,
                                "icon": "folder",
                                "children": [_make_loading_child(f"{key}.{s}")],
                            }
                            for s in schemas
                        ]
                    )
                elif len(parts) == 2:
                    catalog, schema = parts
                    items = self._metastore.list_tables_in_schema_with_types(catalog, schema)
                    node["children"] = (
                        [{"id": f"{key}.__empty__", "label": "(No tables)", "icon": "info"}]
                        if not items
                        else [
                            {
                                "id": f"{key}.{t['name']}",
                                "label": t["name"],
                                "icon": (
                                    "table_chart"
                                    if t["table_type"] == "BASE TABLE"
                                    else "view_list"
                                ),
                                "insertable": True,
                                "draggable": True,
                            }
                            for t in items
                        ]
                    )
                self._loaded.add(key)
                changed = True
            except Exception as exc:
                ui.notify(f"Error loading {key}: {exc}", type="negative")
                node["children"] = [
                    {"id": f"{key}.__error__", "label": f"Error: {exc}", "icon": "error"}
                ]
                changed = True
        if changed:
            self._tree.update()

    def _handle_select(self, e) -> None:
        if not self._on_table_select or not e.value:
            return
        key = e.value
        if len(key.split(".")) == 3 and not key.endswith("__empty__"):
            self._on_table_select(key)

    def _handle_insert(self, node_id: str) -> None:
        if self._on_insert_to_editor:
            self._on_insert_to_editor(node_id)

    def _handle_menu(self, node_id: str) -> None:
        self._context_menu_path = node_id
        if self._context_menu_label is not None:
            self._context_menu_label.set_text(node_id)
        if self._context_menu_dialog is not None:
            self._context_menu_dialog.open()

    def _build_context_menu(self) -> "ui.dialog":
        with ui.dialog() as dialog, ui.card().classes("q-pa-sm").style("min-width: 180px"):
            self._context_menu_label = (
                ui.label("")
                .classes("text-caption text-grey-7 q-mb-xs ellipsis")
                .style("max-width: 200px")
            )
            ui.separator()
            ui.button(
                "Copy path",
                icon="content_copy",
                on_click=lambda: self._copy_path_and_close(),
            ).props("flat align=left").classes("w-full text-body2")
        return dialog

    def _copy_path_and_close(self) -> None:
        path = self._context_menu_path
        ui.run_javascript(f"navigator.clipboard.writeText('{path}')")
        ui.notify(f"Copied: {path}", type="positive", timeout=1500)
        if self._context_menu_dialog is not None:
            self._context_menu_dialog.close()

    def _on_search_change(self, e) -> None:
        self._search_value = (e.value or "").strip()
        self._apply_search_filter()

    def _apply_search_filter(self) -> None:
        query = self._search_value
        if not query:
            self._tree_container.set_visibility(True)
            self._search_results_container.set_visibility(False)
            return

        self._tree_container.set_visibility(False)
        self._search_results_container.set_visibility(True)
        self._render_search_results(query)

    def _select_table(self, path: str) -> None:
        if self._on_table_select:
            self._on_table_select(path)

    def _render_search_results(self, query: str) -> None:
        self._search_results_container.clear()
        matches = self._metastore.search_tables(query)
        with self._search_results_container:
            if not matches:
                ui.label("No tables found.").classes("text-caption text-grey q-pa-sm")
                return

            groups: dict[str, list[dict]] = {}
            for match in matches:
                group_key = f"{match['catalog']}.{match['schema']}"
                groups.setdefault(group_key, []).append(match)

            for group_key, items in groups.items():
                with (
                    ui.expansion(group_key, icon="folder")
                    .classes("w-full")
                    .props("dense default-opened")
                ):
                    for match in items:
                        icon = "table_chart" if match["table_type"] == "BASE TABLE" else "view_list"
                        full_path = match["full_path"]
                        with (
                            ui.row()
                            .classes(
                                "items-center w-full q-px-sm q-py-xs"
                                " cursor-pointer hover:bg-grey-2 rounded"
                            )
                            .on(
                                "click",
                                lambda _, p=full_path: self._select_table(p),
                            )
                        ):
                            ui.icon(icon).classes("text-grey-7 q-mr-xs").style("font-size: 18px")
                            ui.label(match["name"]).classes("text-body2 text-grey-9 col ellipsis")
                            if self._on_insert_to_editor:
                                ui.button(
                                    icon="keyboard_double_arrow_right",
                                    on_click=lambda _, p=full_path: self._on_insert_to_editor(p),  # type: ignore[misc]
                                ).props("flat dense round").classes("text-grey-5").style(
                                    "font-size: 10px"
                                )
                            ui.button(
                                icon="more_vert",
                                on_click=lambda _, p=full_path: self._handle_menu(p),
                            ).props("flat dense round").classes("text-grey-5").style(
                                "font-size: 10px"
                            )


def _default_manager() -> MetastoreManager:
    from app.services.metastore import manager

    return manager


def render_hierarchy_tree(
    container: ui.element,
    on_table_select: Callable[[str], None] | None = None,
    ducklake_manager=None,
    on_insert_to_editor: Callable[[str], None] | None = None,
) -> "CatalogBrowser":
    """Backward-compatible factory function. Returns a CatalogBrowser instance."""
    return CatalogBrowser(
        container=container,
        on_table_select=on_table_select,
        on_insert_to_editor=on_insert_to_editor,
        metastore=ducklake_manager,
    )


def _find_node(nodes: list[dict], node_id: str) -> dict | None:
    """Recursively locate a node by its id."""
    for node in nodes:
        if node["id"] == node_id:
            return node
        found = _find_node(node.get("children", []), node_id)
        if found:
            return found
    return None
