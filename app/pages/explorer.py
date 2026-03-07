"""Metastore Explorer page."""
from nicegui import ui

from app.components.layout import layout_frame
from app.services.ducklake import manager


def _render_empty_state():
    """Render the empty metastore state."""
    ui.label("No tables found in the metastore.").classes(
        "text-subtitle1 text-grey"
    )
    ui.label(
        "Create tables using the Query Editor to see them here."
    ).classes("text-caption text-grey")


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
    table_info = manager.get_table(table_name)
    if table_info is None:
        with schema_container:
            ui.label(f"Table '{table_name}' not found.").classes(
                "text-negative"
            )
        return

    with schema_container:
        ui.label(f"Table: {table_info['name']}").classes(
            "text-h5 q-mb-sm"
        )
        ui.label(
            f"Rows: {table_info['row_count']}"
            f" | Columns: {table_info['column_count']}"
        ).classes("text-caption text-grey q-mb-md")

        columns = [
            {
                "name": "column_name",
                "label": "Column Name",
                "field": "column_name",
                "align": "left",
            },
            {
                "name": "data_type",
                "label": "Data Type",
                "field": "data_type",
                "align": "left",
            },
            {
                "name": "is_nullable",
                "label": "Nullable",
                "field": "is_nullable",
                "align": "left",
            },
        ]
        rows = table_info.get("columns", [])
        ui.table(
            columns=columns, rows=rows, row_key="column_name"
        ).classes("w-full")


def _render_table_list(tables: list[dict]):
    """Render table list with clickable items and schema detail."""
    ui.label(f"{len(tables)} table(s) found").classes(
        "text-subtitle2 text-grey q-mb-md"
    )

    schema_container = ui.column().classes("w-full")

    for t in tables:
        ui.button(
            f"📋 {t['name']}"
            f" ({t['column_count']} cols, {t['row_count']} rows)",
            on_click=lambda _, name=t["name"]: _render_schema(
                schema_container, name
            ),
        ).classes("q-mb-xs").props("flat align=left")


def explorer_page():
    """Render the Metastore Explorer page."""
    layout_frame()

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Metastore Explorer").classes("text-h4 q-mb-md")

        if not manager.is_initialized:
            _render_init_prompt()
            return

        try:
            tables = manager.list_tables()
        except Exception as e:
            ui.label(f"Error loading tables: {e}").classes(
                "text-negative"
            )
            return

        if not tables:
            _render_empty_state()
            return

        _render_table_list(tables)
