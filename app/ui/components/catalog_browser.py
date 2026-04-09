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
        self._search_value: str = ""
        self._render()

    def _render(self) -> None:
        with self._container:
            ui.input(placeholder="Search tables...").classes("w-full q-px-sm q-pt-sm").props(
                "dense clearable"
            ).on("update:model-value", self._on_search_change)
            tree_container = ui.column().classes("w-full")

        initial_nodes = self._load_catalog_nodes()
        with tree_container:
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
                 :draggable="props.node.draggable"
                 @dragstart="$event.dataTransfer.setData('text/plain', props.node.id)">
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
        self._tree.on("insert", lambda e: self._handle_insert(e.args))
        self._tree.on("menu", lambda e: self._handle_menu(e.args))

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
        ui.run_javascript(
            f"navigator.clipboard.writeText('{node_id}')"
            f".then(() => console.log('Copied: {node_id}'))"
        )
        ui.notify(f"Copied: {node_id}", type="positive", timeout=1500)

    def _on_search_change(self, e) -> None:
        self._search_value = (e.args or "").lower()
        self._apply_search_filter()

    def _apply_search_filter(self) -> None:
        if not self._tree:
            return
        query = self._search_value.strip()
        if not query:
            self._tree.props(remove="filter")
        else:
            filter_method = (
                "(node, filter) => node.label.toLowerCase().includes(filter.toLowerCase())"
            )
            self._tree.props(f'filter="{query}" filter-method="{filter_method}"')
        self._tree.update()


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
