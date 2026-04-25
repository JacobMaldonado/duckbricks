"""Shared layout frame for DuckBricks pages."""

from nicegui import ui

from app.config import VERSION


def layout_frame(title: str = "DuckBricks") -> None:
    """Render the shared app shell: header + collapsible left drawer."""
    with ui.header().classes("bg-primary text-white items-center").style("z-index: 2000"):
        ui.button(icon="menu", on_click=lambda: drawer.toggle()).props("flat color=white dense")
        ui.label("🦆 DuckBricks").classes("text-h6 q-ml-sm")
        ui.space()
        ui.label(f"v{VERSION}").classes("text-caption q-mr-md")

    with ui.left_drawer(value=True, bordered=True).classes("bg-grey-1 p-0") as drawer:
        drawer.props("width=200")
        ui.context.client.storage["_ws_nav_drawer"] = drawer
        with ui.list().props("padding").classes("q-pt-sm"):
            with ui.item(on_click=lambda: ui.navigate.to("/explorer")).props("clickable v-ripple"):
                with ui.item_section().props("avatar"):
                    ui.icon("storage").classes("text-grey-7")
                with ui.item_section():
                    ui.label("Metastore Explorer").classes("text-grey-9 text-body2")

            with ui.item(on_click=lambda: ui.navigate.to("/query")).props("clickable v-ripple"):
                with ui.item_section().props("avatar"):
                    ui.icon("code").classes("text-grey-7")
                with ui.item_section():
                    ui.label("Query Editor").classes("text-grey-9 text-body2")

            with ui.item(on_click=lambda: ui.navigate.to("/jobs")).props("clickable v-ripple"):
                with ui.item_section().props("avatar"):
                    ui.icon("schedule").classes("text-grey-7")
                with ui.item_section():
                    ui.label("Jobs").classes("text-grey-9 text-body2")

            with ui.item(on_click=lambda: ui.navigate.to("/workspace")).props("clickable v-ripple"):
                with ui.item_section().props("avatar"):
                    ui.icon("folder_open").classes("text-grey-7")
                with ui.item_section():
                    ui.label("Workspace").classes("text-grey-9 text-body2")
