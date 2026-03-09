"""Metastore Explorer page."""
from nicegui import ui

from app.components.hierarchy_tree import render_hierarchy_tree
from app.components.layout import layout_frame
from app.services.ducklake import manager


def _render_init_prompt():
    """Render initialization prompt when metastore is not ready."""
    ui.label("Metastore is not initialized.").classes(
        "text-subtitle1 text-warning"
    )
    init_button = ui.button("Initialize Metastore", icon="play_arrow")
    status_label = ui.label("").classes("text-caption")

    async def do_init():
        try:
            manager.initialize()
            status_label.set_text(
                "✅ Metastore initialized successfully!"
            )
            ui.navigate.to("/explorer")
        except Exception as e:
            status_label.set_text(f"❌ Error: {e}")

    init_button.on_click(do_init)


def _render_schema(schema_container: ui.column, table_name: str):
    """Render schema detail for a selected table."""
    schema_container.clear()
    
    # Get table schema using the fully qualified name
    try:
        result = manager.execute_query_typed(
            f"DESCRIBE {table_name}"
        )
        
        if not result.get("success"):
            with schema_container:
                ui.label(f"Error loading schema for '{table_name}'").classes(
                    "text-negative q-pa-md"
                )
                ui.label(result.get("error", "Unknown error")).classes(
                    "text-caption text-grey"
                )
            return
        
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        
        with schema_container:
            ui.label(f"Table: {table_name}").classes(
                "text-h5 q-mb-sm q-pa-md"
            )
            
            if not rows:
                ui.label("No column information available.").classes(
                    "text-caption text-grey q-pa-md"
                )
                return
            
            ui.label(f"{len(rows)} column(s)").classes(
                "text-caption text-grey q-mb-md q-px-md"
            )
            
            # Build table columns from DESCRIBE result
            table_columns = [
                {
                    "name": col["name"],
                    "label": f"{col['name']} ({col['type']})",
                    "field": col["name"],
                    "align": "left",
                }
                for col in columns
            ]
            
            # Build rows from result
            col_names = [col["name"] for col in columns]
            table_rows = [
                {
                    name: str(val) if val is not None else ""
                    for name, val in zip(col_names, row)
                }
                for row in rows
            ]
            
            ui.table(
                columns=table_columns,
                rows=table_rows,
                row_key=col_names[0] if col_names else "id"
            ).classes("w-full q-px-md")
    
    except Exception as e:
        with schema_container:
            ui.label(f"Error loading schema for '{table_name}'").classes(
                "text-negative q-pa-md"
            )
            ui.label(str(e)).classes("text-caption text-grey")


def explorer_page():
    """Render the Metastore Explorer page."""
    layout_frame()

    # Disable outer scrolling for consistent layout
    ui.query("body").style("overflow: hidden")
    ui.query(".nicegui-content").classes("p-0").style(
        "padding: 0 !important; "
        "height: calc(100vh - 64px) !important;"
    )

    if not manager.is_initialized:
        with ui.column().classes(
            "q-pa-lg w-full items-center"
        ):
            _render_init_prompt()
        return

    # Two-panel layout: left=hierarchy tree | right=schema details
    with ui.splitter(
        value=30, limits=(15, 50)
    ).classes("w-full").style(
        "height: calc(100vh - 64px)"
    ) as splitter:

        # === LEFT PANEL: Hierarchy Tree ===
        with splitter.before:
            with ui.column().classes("w-full h-full p-0"):
                ui.label("Catalog Browser").classes(
                    "text-subtitle2 q-pa-sm bg-grey-2"
                ).style("margin: 0")
                
                with ui.scroll_area().classes(
                    "w-full"
                ).style("flex: 1"):
                    tree_container = ui.column().classes("w-full")

        # === RIGHT PANEL: Schema Details ===
        with splitter.after:
            with ui.scroll_area().classes("w-full h-full"):
                schema_container = ui.column().classes("w-full")
                with schema_container:
                    ui.label(
                        "Select a table to view its schema"
                    ).classes(
                        "text-subtitle2 text-grey q-pa-md"
                    )

        # Render the hierarchy tree with table selection callback
        def handle_table_selection(table_name: str):
            """Handle table selection from hierarchy tree."""
            _render_schema(schema_container, table_name)

        render_hierarchy_tree(
            tree_container,
            on_table_select=handle_table_selection
        )
