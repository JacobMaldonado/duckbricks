"""Reusable hierarchy tree component for catalog browsing.

Uses NiceGUI's on_expand callback with placeholder children pattern.
Quasar's lazy: True requires a JS done() callback that can't be called
from Python, so we use expandable nodes with placeholder children instead.
When a node is expanded, the placeholder is replaced with real data.
"""

from typing import Callable

from nicegui import ui

from app.services.ducklake import DuckLakeManager


# Placeholder child used to make nodes expandable (shows expand arrow)
_LOADING_ID_PREFIX = "__loading_"


def _make_loading_child(parent_id: str) -> dict:
    """Create a placeholder child that makes the parent expandable."""
    return {
        "id": f"{_LOADING_ID_PREFIX}{parent_id}",
        "label": "Loading...",
        "icon": "hourglass_empty",
    }


def render_hierarchy_tree(
    container: ui.element,
    on_table_select: Callable[[str], None] | None = None,
    on_select: Callable[[str], None] | None = None,
    ducklake_manager: DuckLakeManager | None = None,
) -> ui.tree:
    """Render catalog -> schema -> table hierarchy with on-demand loading.

    Nodes start with a placeholder child so Quasar shows the expand arrow.
    When a user expands a node, the placeholder is swapped with real data
    fetched from the DuckLakeManager service layer.

    Args:
        container: NiceGUI element to render into.
        on_table_select: Optional callback(fully_qualified_table_name). Deprecated, use on_select.
        on_select: Optional callback(node_id) for any node selection.
        ducklake_manager: DuckLakeManager instance (defaults to singleton).

    Returns:
        The ui.tree instance.
    """
    if ducklake_manager is None:
        from app.services.ducklake import manager as ducklake_manager

    # -- build initial catalog nodes --------------------------------
    def _load_catalogs() -> list[dict]:
        if not ducklake_manager.is_initialized:
            return [{
                "id": "__not_initialized__",
                "label": "⚠️ DuckLake not initialized",
                "icon": "warning",
            }]
        try:
            catalogs = ducklake_manager.list_catalogs()
            if not catalogs:
                return [{
                    "id": "__no_catalogs__",
                    "label": "(No catalogs)",
                    "icon": "info",
                }]
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
            return [{
                "id": "__error__",
                "label": f"Error: {exc}",
                "icon": "error",
            }]

    initial_nodes = _load_catalogs()

    # -- render tree ------------------------------------------------
    with container:
        tree = ui.tree(
            initial_nodes,
            node_key="id",
            label_key="label",
            on_select=lambda e: _handle_select(e),
            on_expand=lambda e: _handle_expand(e),
        ).classes("w-full")

    # track which nodes already had their children loaded
    loaded: set[str] = set()

    # -- expand handler ---------------------------------------------
    def _handle_expand(e) -> None:
        """Replace placeholder children with real data on expand."""
        expanded_keys: list = e.value if isinstance(e.value, list) else [e.value]

        changed = False
        for key in expanded_keys:
            if key in loaded or key.startswith("__"):
                continue

            node = _find_node(tree._props["nodes"], key)
            if node is None:
                continue

            # check if children are just the loading placeholder
            children = node.get("children", [])
            if children and not children[0]["id"].startswith(_LOADING_ID_PREFIX):
                # already loaded (e.g. user collapsed then re-expanded)
                loaded.add(key)
                continue

            parts = key.split(".")
            try:
                if len(parts) == 1:
                    # catalog -> load schemas
                    schemas = ducklake_manager.list_schemas(parts[0])
                    if not schemas:
                        node["children"] = [{
                            "id": f"{key}.__empty__",
                            "label": "(No schemas)",
                            "icon": "info",
                        }]
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
                    # schema -> load tables
                    catalog, schema = parts
                    tables = ducklake_manager.list_tables_in_schema(catalog, schema)
                    if not tables:
                        node["children"] = [{
                            "id": f"{key}.__empty__",
                            "label": "(No tables)",
                            "icon": "info",
                        }]
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
                node["children"] = [{
                    "id": f"{key}.__error__",
                    "label": f"Error: {exc}",
                    "icon": "error",
                }]
                changed = True

        if changed:
            tree.update()

    # -- select handler ---------------------------------------------
    def _handle_select(e) -> None:
        if not e.value:
            return
        key = e.value
        
        # Skip placeholder/error nodes
        if key.startswith("__"):
            return
        
        # Call the generic on_select if provided
        if on_select:
            on_select(key)
        # Fall back to on_table_select for backward compatibility
        elif on_table_select:
            parts = key.split(".")
            # only fire for table-level nodes (catalog.schema.table)
            if len(parts) == 3:
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
