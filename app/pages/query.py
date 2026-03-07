"""Execution Environment page."""
from nicegui import ui

from app.components.layout import layout_frame


def query_page():
    """Render the SQL Query Editor page (stub for now)."""
    layout_frame()
    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Query Editor").classes("text-h4")
        ui.label(
            "SQL execution environment coming soon..."
        ).classes("text-subtitle1 text-grey")
