"""Reusable hierarchy tree component for catalog browsing.

Uses NiceGUI's on_expand callback with placeholder children pattern.
Quasar's lazy: True requires a JS done() callback that can't be called
from Python, so we use expandable nodes with placeholder children instead.
When a node is expanded, the placeholder is replaced with real data.
"""

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


def render_hierarchy_tree(
    container: ui.element,
    on_table_select: Callable[[str], None] | None = None,
    ducklake_manager: MetastoreManager | None = None,
) -> ui.tree:
    """Render catalog -> schema -> table hierarchy with on-demand loading.

    Args:
        container: NiceGUI element to render into.
        on_table_select: Optional callback(fully_qualified_table_name).
        ducklake_manager: MetastoreManager instance (defaults to singleton).

    Returns:
        The ui.tree instance.
    """
    if ducklake_manager is None:
        from app.services.metastore import manager as ducklake_manager

    def _load_catalogs() -> list[dict]:
        if not ducklake_manager.is_initialized:
            return [
                {
                    "id": "__not_initialized__",
                    "label": "⚠️ DuckLake not initialized",
                    "icon": "warning",
                }
            ]
        try:
            catalogs = ducklake_manager.list_catalogs()
            if not catalogs:
                return [
                    {
                        "id": "__no_catalogs__",
                        "label": "(No catalogs)",
                        "icon": "info",
                    }
                ]
            return [
                {
                    "id": cat,
                    "label": cat,
                    "icon": "storage",
                    "children": [_make_loading_child(cat)],
                }
                for cat in catalogs
            ]
        except Exception as exc:
            ui.notify(f"Failed to load catalogs: {exc}", type="negative")
            return [
                {
                    "id": "__error__",
                    "label": f"Error: {exc}",
                    "icon": "error",
                }
            ]

    initial_nodes = _load_catalogs()

    with container:
        tree = ui.tree(
            initial_nodes,
            node_key="id",
            label_key="label",
            on_select=lambda e: _handle_select(e),
            on_expand=lambda e: _handle_expand(e),
        ).classes("w-full")

    loaded: set[str] = set()

    def _handle_expand(e) -> None:
        expanded_keys: list = e.value if isinstance(e.value, list) else [e.value]

        changed = False
        for key in expanded_keys:
            if key in loaded or key.startswith("__"):
                continue

            node = _find_node(tree._props["nodes"], key)
            if node is None:
                continue

            children = node.get("children", [])
            if children and not children[0]["id"].startswith(_LOADING_ID_PREFIX):
                loaded.add(key)
                continue

            parts = key.split(".")
            try:
                if len(parts) == 1:
                    schemas = ducklake_manager.list_schemas(parts[0])
                    if not schemas:
                        node["children"] = [
                            {
                                "id": f"{key}.__empty__",
                                "label": "(No schemas)",
                                "icon": "info",
                            }
                        ]
                    else:
                        node["children"] = [
                            {
                                "id": f"{key}.{s}",
                                "label": s,
                                "icon": "folder",
                                "children": [_make_loading_child(f"{key}.{s}")],
                            }
                            for s in schemas
                        ]
                elif len(parts) == 2:
                    catalog, schema = parts
                    tables = ducklake_manager.list_tables_in_schema(catalog, schema)
                    if not tables:
                        node["children"] = [
                            {
                                "id": f"{key}.__empty__",
                                "label": "(No tables)",
                                "icon": "info",
                            }
                        ]
                    else:
                        node["children"] = [
                            {
                                "id": f"{key}.{t}",
                                "label": t,
                                "icon": "table_chart",
                            }
                            for t in tables
                        ]
                loaded.add(key)
                changed = True
            except Exception as exc:
                ui.notify(f"Error loading {key}: {exc}", type="negative")
                node["children"] = [
                    {
                        "id": f"{key}.__error__",
                        "label": f"Error: {exc}",
                        "icon": "error",
                    }
                ]
                changed = True

        if changed:
            tree.update()

    def _handle_select(e) -> None:
        if not on_table_select or not e.value:
            return
        key = e.value
        parts = key.split(".")
        if len(parts) == 3 and not key.endswith("__empty__"):
            on_table_select(key)

    return tree


def _find_node(nodes: list[dict], node_id: str) -> dict | None:
    """Recursively locate a node by its id."""
    for node in nodes:
        if node["id"] == node_id:
            return node
        found = _find_node(node.get("children", []), node_id)
        if found:
            return found
    return None
