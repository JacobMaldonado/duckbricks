"""Metastore Explorer page."""
from nicegui import ui

from app.components.layout import layout_frame


def explorer_page():
    """Render the Metastore Explorer page (stub for now)."""
    layout_frame()
    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Metastore Explorer").classes("text-h4")
        ui.label(
            "Table listing and schema inspection coming soon..."
        ).classes("text-subtitle1 text-grey")
