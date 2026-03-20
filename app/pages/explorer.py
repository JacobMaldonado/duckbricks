"""Metastore Explorer page."""
from nicegui import ui

from app.components.hierarchy_tree import render_hierarchy_tree
from app.components.layout import layout_frame
from app.services.ducklake import manager


def _show_create_catalog_dialog(tree_container: ui.element):
    """Show the create catalog modal dialog."""
    catalog_name = ""
    description = ""
    storage_path = ""

    with ui.dialog() as dialog, ui.card().classes("w-full").style("min-width: 500px; max-width: 600px"):
        # Dialog header
        with ui.row().classes("w-full items-center justify-between q-pb-md").style(
            "border-bottom: 1px solid #E5E5E5"
        ):
            with ui.row().classes("items-center gap-2"):
                ui.icon("storage", size="24px").classes("text-primary")
                ui.label("Create New Catalog").classes("text-h6 text-weight-medium")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        # Dialog body
        with ui.column().classes("w-full gap-4 q-py-md"):
            # Catalog name
            ui.label("Catalog Name *").classes("text-body2 text-weight-medium")
            name_input = ui.input(
                placeholder="e.g., production, analytics, ml_models"
            ).props('outlined dense').classes("w-full")
            ui.label(
                "Use lowercase letters, numbers, and underscores only"
            ).classes("text-caption text-grey-7 q-mt-n3")

            # Description
            ui.label("Description (optional)").classes("text-body2 text-weight-medium q-mt-sm")
            desc_input = ui.textarea(
                placeholder="Brief description of this catalog's purpose..."
            ).props('outlined').classes("w-full").style("min-height: 80px")

            # Storage location
            ui.label("Storage Location (optional)").classes("text-body2 text-weight-medium q-mt-sm")
            path_input = ui.input(
                placeholder="/data/catalogs/production"
            ).props('outlined dense').classes("w-full")
            ui.label(
                "Defaults to system configuration if not specified"
            ).classes("text-caption text-grey-7 q-mt-n3")

            # Info callout
            with ui.card().classes("bg-blue-1 q-mt-sm").style("border-left: 3px solid #0066CC"):
                with ui.row().classes("items-start gap-2 q-pa-sm"):
                    ui.icon("info", size="20px").classes("text-primary q-mt-1")
                    with ui.column().classes("flex-grow"):
                        ui.label("Catalog Naming Guidelines").classes(
                            "text-caption text-weight-medium"
                        )
                        ui.label(
                            "• Must be unique across your metastore\n"
                            "• Use descriptive names that indicate purpose\n"
                            "• Cannot be renamed after creation"
                        ).classes("text-caption text-grey-8").style("white-space: pre-line")

        # Dialog footer
        with ui.row().classes("w-full justify-end gap-2 q-pt-md").style(
            "border-top: 1px solid #E5E5E5"
        ):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            create_btn = ui.button("Create Catalog", icon="add").classes("bg-primary text-white")

        # Handle create action
        async def handle_create():
            name = name_input.value.strip()
            if not name:
                ui.notify("Catalog name is required", type="warning")
                return

            result = manager.create_catalog(
                name=name,
                description=desc_input.value.strip(),
                storage_path=path_input.value.strip()
            )

            if result["success"]:
                ui.notify(result["message"], type="positive")
                dialog.close()
                # Refresh the tree by reloading the hierarchy
                tree_container.clear()
                render_hierarchy_tree(tree_container)
            else:
                ui.notify(result["error"], type="negative")

        create_btn.on_click(handle_create)

    dialog.open()


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
                # Header with Create button
                with ui.row().classes("w-full items-center justify-between q-pa-sm bg-grey-2"):
                    ui.label("Catalog Browser").classes("text-subtitle2")
                    ui.button(
                        icon="add",
                        on_click=lambda: _show_create_catalog_dialog(tree_container)
                    ).props("flat dense round").tooltip("Create Catalog")
                
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
