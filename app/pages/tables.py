"""Tables view page - shows all tables within a schema."""
from nicegui import ui

from app.components.layout import layout_frame
from app.services.ducklake import manager


def _format_number(num: int) -> str:
    """Format large numbers with K/M suffix."""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return str(num)


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable format."""
    if size_bytes < 0:
        return "N/A"
    elif size_bytes >= 1_073_741_824:  # GB
        return f"{size_bytes / 1_073_741_824:.1f} GB"
    elif size_bytes >= 1_048_576:  # MB
        return f"{size_bytes / 1_048_576:.1f} MB"
    elif size_bytes >= 1_024:  # KB
        return f"{size_bytes / 1_024:.1f} KB"
    else:
        return f"{size_bytes} B"


def _render_table_card(catalog: str, schema: str, table_info: dict):
    """Render a single table card."""
    name = table_info["name"]
    rows = table_info["row_count"]
    columns = table_info["column_count"]
    size = table_info["size_bytes"]
    
    with ui.card().classes("w-full cursor-pointer hover:shadow-lg transition-shadow").on(
        "click", lambda: ui.navigate.to(f"/table/{catalog}/{schema}/{name}")
    ):
        with ui.row().classes("w-full items-center"):
            # Icon
            ui.icon("table_chart", size="32px").classes("text-primary")
            
            # Content
            with ui.column().classes("flex-grow q-ml-md"):
                ui.label(name).classes("text-h6 text-weight-medium")
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("format_list_numbered", size="16px").classes("text-grey-6")
                        ui.label(f"{_format_number(rows)} rows").classes("text-caption text-grey-7")
                    ui.label("•").classes("text-caption text-grey-5")
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("storage", size="16px").classes("text-grey-6")
                        ui.label(_format_size(size)).classes("text-caption text-grey-7")
                    ui.label("•").classes("text-caption text-grey-5")
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("view_column", size="16px").classes("text-grey-6")
                        ui.label(f"{columns} columns").classes("text-caption text-grey-7")
            
            # Action icon
            ui.icon("chevron_right", size="24px").classes("text-grey-5")


def _render_empty_state(catalog: str, schema: str):
    """Render empty state when no tables exist."""
    with ui.column().classes("w-full items-center justify-center q-mt-xl q-pt-xl"):
        # Empty state illustration
        ui.icon("table_chart", size="128px").classes("text-grey-4 q-mb-md")
        
        # Empty state content
        ui.label("No tables in this schema").classes("text-h4 text-weight-bold q-mb-sm")
        ui.label(
            "Create your first table to start storing structured data"
        ).classes("text-body1 text-grey-7 q-mb-lg").style("max-width: 450px; text-align: center")


def tables_page(catalog: str, schema: str):
    """Render the tables page for a given catalog and schema."""
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
    
    # Get schema stats and tables
    try:
        stats = manager.get_schema_table_stats(catalog, schema)
        table_names = manager.list_tables_in_schema(catalog, schema)
        
        # Get details for each table
        tables = []
        for table_name in table_names:
            details = manager.get_table_details(catalog, schema, table_name)
            tables.append(details)
    
    except Exception as e:
        with ui.column().classes("w-full max-w-screen-xl mx-auto q-pa-lg"):
            ui.label(f"Error loading schema: {e}").classes("text-negative")
        return
    
    # Main content container
    with ui.column().classes("w-full max-w-screen-xl mx-auto q-pa-lg"):
        # Breadcrumbs
        with ui.row().classes("items-center gap-1 q-mb-md"):
            ui.link("Catalogs", "/explorer").classes("text-body2 text-grey-7")
            ui.label("›").classes("text-grey-5")
            ui.link(catalog, f"/schemas/{catalog}").classes("text-body2 text-grey-7")
            ui.label("›").classes("text-grey-5")
            ui.label(schema).classes("text-body2 text-weight-medium")
        
        # Page header
        with ui.row().classes("w-full items-center justify-between q-mb-md"):
            with ui.column():
                with ui.row().classes("items-center gap-2"):
                    ui.icon("folder", size="32px").classes("text-primary")
                    ui.label(schema).classes("text-h4 text-weight-bold")
                ui.label("Tables in this schema").classes("text-body2 text-grey-7")
        
        # Check if tables exist
        if not tables:
            _render_empty_state(catalog, schema)
            return
        
        # Search and filter bar
        search_container = ui.column().classes("w-full")
        with search_container:
            with ui.row().classes("w-full items-center gap-4 q-mb-md"):
                search_input = ui.input(placeholder="Search tables...").props(
                    'outlined dense prepend-inner-icon="search"'
                ).classes("flex-grow")
        
        # Stats row
        with ui.row().classes("w-full gap-4 q-mb-lg"):
            with ui.card().classes("flex-1"):
                with ui.column().classes("q-pa-md"):
                    ui.label("Tables").classes("text-caption text-grey-7")
                    ui.label(str(stats["table_count"])).classes("text-h4 text-weight-bold text-primary")
            
            with ui.card().classes("flex-1"):
                with ui.column().classes("q-pa-md"):
                    ui.label("Total Rows").classes("text-caption text-grey-7")
                    ui.label(_format_number(stats["total_rows"])).classes("text-h4 text-weight-bold")
        
        # Tables list header
        ui.label("Tables").classes("text-h6 text-weight-medium q-mb-sm")
        
        # Tables grid (with search filter support)
        tables_container = ui.column().classes("w-full gap-3")
        
        def render_filtered_tables(filter_text: str = ""):
            """Render tables based on search filter."""
            tables_container.clear()
            
            filtered = [
                t for t in tables 
                if filter_text.lower() in t["name"].lower()
            ] if filter_text else tables
            
            with tables_container:
                if not filtered:
                    ui.label("No tables match your search").classes("text-grey-6 q-pa-md")
                else:
                    for table in filtered:
                        _render_table_card(catalog, schema, table)
        
        # Initial render
        render_filtered_tables()
        
        # Wire up search
        search_input.on("input", lambda e: render_filtered_tables(e.value))
