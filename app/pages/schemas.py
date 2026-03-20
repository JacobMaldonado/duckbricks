"""Schemas view page - shows all schemas within a catalog."""
from nicegui import ui

from app.components.layout import layout_frame
from app.services.ducklake import manager


def _render_schema_card(catalog: str, schema_name: str, table_count: int):
    """Render a single schema card."""
    with ui.card().classes("w-full cursor-pointer hover:shadow-lg transition-shadow").on(
        "click", lambda: ui.navigate.to(f"/tables/{catalog}/{schema_name}")
    ):
        with ui.row().classes("w-full items-center"):
            # Icon
            ui.icon("folder", size="32px").classes("text-primary")
            
            # Content
            with ui.column().classes("flex-grow q-ml-md"):
                ui.label(schema_name).classes("text-h6 text-weight-medium")
                with ui.row().classes("items-center gap-2"):
                    ui.icon("table_chart", size="16px").classes("text-grey-6")
                    table_text = "table" if table_count == 1 else "tables"
                    ui.label(f"{table_count} {table_text}").classes("text-caption text-grey-7")
            
            # Action icon
            ui.icon("chevron_right", size="24px").classes("text-grey-5")


def _render_empty_state(catalog: str):
    """Render empty state when no schemas exist."""
    with ui.column().classes("w-full items-center justify-center q-mt-xl q-pt-xl"):
        # Empty state illustration
        ui.icon("folder_open", size="128px").classes("text-grey-4 q-mb-md")
        
        # Empty state content
        ui.label("No schemas in this catalog").classes("text-h4 text-weight-bold q-mb-sm")
        ui.label(
            "Create your first schema to organize tables within this catalog"
        ).classes("text-body1 text-grey-7 q-mb-lg").style("max-width: 450px; text-align: center")


def schemas_page(catalog: str):
    """Render the schemas page for a given catalog."""
    layout_frame()
    
    # Styling
    ui.query("body").style("overflow: hidden")
    ui.query(".nicegui-content").style(
        "height: calc(100vh - 64px); overflow-y: auto; background-color: #FAFAFA"
    )
    
    if not manager.is_initialized:
        with ui.column().classes("w-full max-w-screen-xl mx-auto q-pa-lg"):
            ui.label("Metastore is not initialized.").classes("text-subtitle1 text-warning")
        return
    
    # Get catalog stats and schemas
    try:
        stats = manager.get_catalog_stats(catalog)
        schema_names = manager.list_schemas(catalog)
        
        # Get details for each schema
        schemas = []
        for schema_name in schema_names:
            details = manager.get_schema_details(catalog, schema_name)
            schemas.append(details)
    
    except Exception as e:
        with ui.column().classes("w-full max-w-screen-xl mx-auto q-pa-lg"):
            ui.label(f"Error loading catalog: {e}").classes("text-negative")
        return
    
    # Main content container
    with ui.column().classes("w-full max-w-screen-xl mx-auto q-pa-lg"):
        # Breadcrumbs
        with ui.row().classes("items-center gap-1 q-mb-md"):
            ui.link("Catalogs", "/explorer").classes("text-body2 text-grey-7")
            ui.label("›").classes("text-grey-5")
            ui.label(catalog).classes("text-body2 text-weight-medium")
        
        # Page header
        with ui.row().classes("w-full items-center justify-between q-mb-md"):
            with ui.column():
                with ui.row().classes("items-center gap-2"):
                    ui.icon("storage", size="32px").classes("text-primary")
                    ui.label(catalog).classes("text-h4 text-weight-bold")
                ui.label("Schemas in this catalog").classes("text-body2 text-grey-7")
        
        # Check if schemas exist
        if not schemas:
            _render_empty_state(catalog)
            return
        
        # Search bar
        search_container = ui.column().classes("w-full")
        with search_container:
            with ui.row().classes("w-full q-mb-md"):
                search_input = ui.input(placeholder="Search schemas...").props(
                    'outlined dense prepend-inner-icon="search"'
                ).classes("flex-grow")
        
        # Stats row
        with ui.row().classes("w-full gap-4 q-mb-lg"):
            with ui.card().classes("flex-1"):
                with ui.column().classes("q-pa-md"):
                    ui.label("Schemas").classes("text-caption text-grey-7")
                    ui.label(str(stats["schema_count"])).classes("text-h4 text-weight-bold text-primary")
            
            with ui.card().classes("flex-1"):
                with ui.column().classes("q-pa-md"):
                    ui.label("Total Tables").classes("text-caption text-grey-7")
                    ui.label(str(stats["total_tables"])).classes("text-h4 text-weight-bold")
        
        # Schemas list header
        ui.label("Schemas").classes("text-h6 text-weight-medium q-mb-sm")
        
        # Schemas grid (with search filter support)
        schemas_container = ui.column().classes("w-full gap-3")
        
        def render_filtered_schemas(filter_text: str = ""):
            """Render schemas based on search filter."""
            schemas_container.clear()
            
            filtered = [
                s for s in schemas 
                if filter_text.lower() in s["name"].lower()
            ] if filter_text else schemas
            
            with schemas_container:
                if not filtered:
                    ui.label("No schemas match your search").classes("text-grey-6 q-pa-md")
                else:
                    for schema in filtered:
                        _render_schema_card(catalog, schema["name"], schema["table_count"])
        
        # Initial render
        render_filtered_schemas()
        
        # Wire up search
        search_input.on("input", lambda e: render_filtered_schemas(e.value))
