"""Shared layout frame for DuckBricks pages."""
from nicegui import ui

from app.config import VERSION


def layout_frame(title: str = "DuckBricks"):
    """Create the shared page layout with header and navigation."""
    # Dark header bar with app title
    with ui.header().classes("bg-primary text-white"):
        ui.label("🦆 DuckBricks").classes("text-h6 q-ml-md")
        # Navigation links
        ui.link("Catalogs", "/catalogs").classes("text-white q-ml-lg")
        ui.link("Metastore Explorer", "/explorer").classes("text-white q-ml-md")
        ui.link("Query Editor", "/query").classes("text-white q-ml-md")
        # Spacer to push items apart
        ui.space()
        ui.label(f"v{VERSION}").classes("text-caption q-mr-md")
