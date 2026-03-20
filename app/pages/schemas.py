"""Schemas list page - shows all schemas within a catalog."""
from nicegui import ui

from app.components.layout import layout_frame
from app.services.ducklake import manager


def schemas_page(catalog: str):
    """Render the schemas list page for a specific catalog."""
    layout_frame()
    
    with ui.column().classes("w-full q-pa-lg gap-4"):
        # Breadcrumb navigation
        with ui.row().classes("items-center gap-2"):
            ui.link("Catalogs", "/catalogs").classes("text-primary")
            ui.label("/").classes("text-grey-6")
            ui.label(catalog).classes("text-weight-medium")
        
        # Page header
        with ui.row().classes("w-full items-center justify-between q-mb-md"):
            with ui.column():
                ui.label(f"Schemas in {catalog}").classes("text-h4")
                ui.label(f"Browse and manage schemas within the {catalog} catalog").classes(
                    "text-caption text-grey-7"
                )
        
        # Get schemas list
        try:
            schemas_result = manager.list_schemas_in_catalog(catalog)
            
            if not schemas_result.get("success"):
                ui.label(f"Error loading schemas: {schemas_result.get('error', 'Unknown error')}").classes(
                    "text-negative"
                )
                return
            
            schemas = schemas_result.get("schemas", [])
            
            if not schemas:
                # Empty state
                with ui.card().classes("w-full q-pa-lg text-center"):
                    ui.icon("folder_open", size="64px").classes("text-grey-5")
                    ui.label("No schemas yet").classes("text-h6 text-grey-7 q-mt-md")
                    ui.label(f"Create your first schema in the {catalog} catalog").classes(
                        "text-caption text-grey-6"
                    )
                    ui.button("Go to Explorer", icon="arrow_forward", on_click=lambda: ui.navigate.to("/explorer")).classes(
                        "q-mt-md"
                    )
            else:
                # Schemas grid
                with ui.grid(columns=3).classes("w-full gap-4"):
                    for schema in schemas:
                        with ui.card().classes("cursor-pointer hover:shadow-lg transition-all"):
                            with ui.card_section().classes("q-pa-md"):
                                with ui.row().classes("items-center gap-2 q-mb-sm"):
                                    ui.icon("folder", size="24px").classes("text-primary")
                                    ui.label(schema).classes("text-subtitle1 text-weight-medium")
                                
                                ui.label("Schema").classes("text-caption text-grey-6")
                                
                                # Click to view details (for now, just go back to explorer)
                                ui.button(
                                    "View Tables",
                                    icon="arrow_forward",
                                    on_click=lambda s=schema: ui.navigate.to("/explorer")
                                ).props("flat").classes("q-mt-sm")
        
        except Exception as e:
            with ui.card().classes("w-full q-pa-md"):
                ui.label(f"Error: {str(e)}").classes("text-negative")
                ui.label("Failed to load schemas list").classes("text-caption text-grey-7")
