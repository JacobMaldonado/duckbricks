"""Shared layout frame for DuckBricks pages."""

from nicegui import ui

from app.config import VERSION
from app.ui.components.navigation import NavigationDrawer


def layout_frame(title: str = "DuckBricks") -> None:
    """Render the shared app shell: header + collapsible left drawer."""
    navigation = NavigationDrawer(ui.context.client.request.url.path)

    with ui.header().classes("bg-primary text-white items-center").style("z-index: 2000"):
        ui.button(icon="menu", on_click=navigation.toggle_visibility).props(
            "flat color=white dense"
        )
        ui.label("🦆 DuckBricks").classes("text-h6 q-ml-sm")
        ui.space()
        ui.label(f"v{VERSION}").classes("text-caption q-mr-md")

    navigation.render()

    ui.query(".nicegui-content").classes("p-0").style("padding: 0 !important;")
