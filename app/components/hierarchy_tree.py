"""Reusable hierarchy tree component for Catalog → Schema → Table navigation."""
from typing import Callable

from nicegui import ui

from app.constants.ui_style import TREE_COLORS, TREE_ICONS
from app.services.ducklake import DuckLakeManager, manager


def render_hierarchy_tree(
    container: ui.element,
    on_table_select: Callable[[str], None] | None = None,
    ducklake_service: DuckLakeManager | None = None,
    style_config: dict | None = None
) -> ui.tree:
    """
    Render a Catalog → Schema → Table hierarchy tree with lazy loading.
    
    Args:
        container: NiceGUI container to render into
        on_table_select: Callback invoked when a table is clicked (receives fully qualified table name)
        ducklake_service: DuckLakeManager instance (defaults to singleton if None)
        style_config: Optional dict for icon/style overrides
    
    Returns:
        The ui.tree instance
    """
    service = ducklake_service or manager
    icons = style_config.get('icons', TREE_ICONS) if style_config else TREE_ICONS
    colors = style_config.get('colors', TREE_COLORS) if style_config else TREE_COLORS
    
    def load_catalogs() -> list[dict]:
        """Load top-level catalog nodes."""
        if not service.is_initialized:
            return [{
                "id": "error:not_initialized",
                "label": "⚠️ Metastore not initialized",
                "icon": icons['error'],
            }]
        
        try:
            catalogs = service.list_catalogs()
            if not catalogs:
                return [{
                    "id": "placeholder:no_catalogs",
                    "label": "(No catalogs)",
                    "icon": icons['error'],
                }]
            
            return [
                {
                    "id": f"catalog:{cat}",
                    "label": cat,
                    "icon": icons['catalog'],
                    "children": [],
                }
                for cat in catalogs
            ]
        except Exception as e:
            ui.notify(f"Error loading catalogs: {e}", type='negative')
            return [{
                "id": "error:catalog_load",
                "label": f"❌ Error: {e}",
                "icon": icons['error'],
            }]
    
    nodes = load_catalogs()
    
    with container:
        tree = ui.tree(
            nodes=nodes,
            node_key="id",
            label_key="label",
        ).classes("w-full")
    
    async def on_expand(e):
        """Lazy-load children when a node is expanded."""
        expanded_ids = e.value if isinstance(e.value, set) else {e.value}
        
        for node_id in expanded_ids:
            node = _find_node(tree._props["nodes"], node_id)
            if node is None:
                continue
            
            # Skip if children already loaded (and not a placeholder)
            if node.get("children") and len(node["children"]) > 0:
                first_child_id = node["children"][0].get("id", "")
                if not first_child_id.startswith("placeholder:"):
                    continue
            
            # Parse node ID
            if not node_id.startswith("catalog:") and not node_id.startswith("schema:"):
                continue
            
            parts = node_id.split(":")
            if len(parts) < 2:
                continue
            
            node_type, node_path = parts[0], parts[1]
            
            try:
                if node_type == "catalog":
                    # Load schemas for this catalog
                    catalog = node_path
                    schemas = service.list_schemas(catalog)
                    
                    if not schemas:
                        node["children"] = [{
                            "id": f"placeholder:{catalog}:no_schemas",
                            "label": "(No schemas)",
                            "icon": icons['error'],
                        }]
                    else:
                        node["children"] = [
                            {
                                "id": f"schema:{catalog}.{schema}",
                                "label": schema,
                                "icon": icons['schema'],
                                "children": [],
                            }
                            for schema in schemas
                        ]
                
                elif node_type == "schema":
                    # Load tables for this schema
                    path_parts = node_path.split(".")
                    if len(path_parts) != 2:
                        continue
                    
                    catalog, schema = path_parts
                    tables = service.list_tables_in_schema(catalog, schema)
                    
                    if not tables:
                        node["children"] = [{
                            "id": f"placeholder:{catalog}.{schema}:no_tables",
                            "label": "(No tables)",
                            "icon": icons['error'],
                        }]
                    else:
                        node["children"] = [
                            {
                                "id": f"table:{catalog}.{schema}.{table}",
                                "label": table,
                                "icon": icons['table'],
                            }
                            for table in tables
                        ]
            
            except Exception as e:
                ui.notify(f"Error expanding {node_id}: {e}", type='negative')
                node["children"] = [{
                    "id": f"error:{node_id}",
                    "label": f"❌ Error: {e}",
                    "icon": icons['error'],
                }]
        
        tree.update()
    
    async def on_select(e):
        """Handle node selection."""
        if not on_table_select:
            return
        
        selected_ids = e.value if isinstance(e.value, list) else [e.value]
        
        for node_id in selected_ids:
            if node_id.startswith("table:"):
                # Extract fully qualified table name
                table_path = node_id.split(":", 1)[1]
                on_table_select(table_path)
                break
    
    tree.on("expand", on_expand)
    tree.on("select", on_select)
    
    return tree


def _find_node(nodes: list[dict], node_id: str) -> dict | None:
    """Recursively find a node by ID in the tree."""
    for node in nodes:
        if node["id"] == node_id:
            return node
        children = node.get("children", [])
        if children:
            found = _find_node(children, node_id)
            if found:
                return found
    return None
