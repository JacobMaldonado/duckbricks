"""Reusable hierarchy tree component for catalog browsing."""

from typing import Callable

from nicegui import ui

from app.services.ducklake import DuckLakeManager


def render_hierarchy_tree(
    container: ui.element,
    on_table_select: Callable[[str], None] | None = None,
    ducklake_manager: DuckLakeManager | None = None,
) -> ui.tree:
    """Render catalog → schema → table hierarchy with lazy loading.

    This component implements a three-level hierarchy tree that lazy-loads
    children on demand when nodes are expanded.

    Args:
        container: NiceGUI container to render the tree into
        on_table_select: Optional callback invoked when table selected
                         (receives fully qualified table name: catalog.schema.table)
        ducklake_manager: Optional DuckLakeManager instance (defaults to singleton)

    Returns:
        Configured ui.tree component

    Note:
        Nodes use "lazy: True" property to be expandable without children.
        Node IDs follow format: catalog → catalog.schema → catalog.schema.table
    """
    # Import default manager if not provided
    if ducklake_manager is None:
        from app.services.ducklake import manager as ducklake_manager

    def load_catalogs() -> list[dict]:
        """Load top-level catalog nodes."""
        if not ducklake_manager.is_initialized:
            return [
                {
                    "id": "__not_initialized__",
                    "label": "⚠️ DuckLake not initialized",
                    "icon": "error",
                }
            ]

        try:
            catalogs = ducklake_manager.list_catalogs()
            if not catalogs:
                return [
                    {
                        "id": "__empty_catalogs__",
                        "label": "No catalogs available",
                        "icon": "info",
                    }
                ]

            return [
                {
                    "id": cat,
                    "label": f"📦 {cat}",
                    "lazy": True,  # KEY FIX: marks as expandable without children
                }
                for cat in catalogs
            ]
        except Exception as e:
            ui.notify(f"Failed to load catalogs: {e}", type="negative")
            return [
                {
                    "id": "__error_catalogs__",
                    "label": f"⚠️ Error loading catalogs: {str(e)}",
                    "icon": "error",
                }
            ]

    # Initialize tree with catalog nodes
    nodes = load_catalogs()

    with container:
        tree = ui.tree(nodes, node_key="id", label_key="label").classes("w-full")

    # Track which nodes have been loaded to avoid re-loading
    loaded_nodes: set[str] = set()

    async def on_expand_handler(e):
        """Handle node expansion - lazy load children."""
        # e.value contains set/list of currently expanded node IDs
        expanded_ids = e.value if isinstance(e.value, (list, set)) else [e.value]

        for node_id in expanded_ids:
            # Skip if already loaded
            if node_id in loaded_nodes:
                continue

            # Find the node in the tree - FIX: use tree.props not tree._props
            node = _find_node(tree.props["nodes"], node_id)
            if node is None:
                continue

            # Skip special nodes (error/empty indicators)
            if node["id"].startswith("__"):
                continue

            # Determine node level by counting dots in ID
            parts = node_id.split(".")

            try:
                if len(parts) == 1:
                    # Catalog node - load schemas
                    catalog = parts[0]
                    schemas = ducklake_manager.list_schemas(catalog)

                    if not schemas:
                        node["children"] = [
                            {
                                "id": f"{catalog}.__empty_schemas__",
                                "label": "No schemas available",
                                "icon": "info",
                            }
                        ]
                    else:
                        node["children"] = [
                            {
                                "id": f"{catalog}.{schema}",
                                "label": f"📂 {schema}",
                                "lazy": True,
                            }
                            for schema in schemas
                        ]

                elif len(parts) == 2:
                    # Schema node - load tables
                    catalog, schema = parts
                    tables = ducklake_manager.list_tables_in_schema(catalog, schema)

                    if not tables:
                        node["children"] = [
                            {
                                "id": f"{catalog}.{schema}.__empty_tables__",
                                "label": "No tables available",
                                "icon": "info",
                            }
                        ]
                    else:
                        node["children"] = [
                            {
                                "id": f"{catalog}.{schema}.{table}",
                                "label": f"📋 {table}",
                                # No lazy property - this is a leaf node
                            }
                            for table in tables
                        ]

                # Remove lazy property after loading children
                node.pop("lazy", None)
                loaded_nodes.add(node_id)

            except Exception as e:
                ui.notify(f"Failed to load children for {node_id}: {e}", type="negative")
                node["children"] = [
                    {
                        "id": f"{node_id}.__error__",
                        "label": f"⚠️ Error: {str(e)}",
                        "icon": "error",
                    }
                ]
                node.pop("lazy", None)

        # Update the tree to reflect changes
        tree.update()

    async def on_select_handler(e):
        """Handle node selection - invoke callback for table selections."""
        if not e.value or not on_table_select:
            return

        node_id = e.value
        parts = node_id.split(".")

        # Only handle table selections (3 parts: catalog.schema.table)
        if len(parts) == 3 and not node_id.endswith("__empty_tables__"):
            # Pass the fully qualified table name
            on_table_select(node_id)

    # Register event handlers
    tree.on("expand", on_expand_handler)
    tree.on("select", on_select_handler)

    return tree


def _find_node(nodes: list[dict], node_id: str) -> dict | None:
    """Recursively find a node by ID in the tree structure.

    Args:
        nodes: List of node dictionaries
        node_id: ID of the node to find

    Returns:
        Node dictionary if found, None otherwise
    """
    for node in nodes:
        if node["id"] == node_id:
            return node
        children = node.get("children", [])
        if children:
            found = _find_node(children, node_id)
            if found:
                return found
    return None
