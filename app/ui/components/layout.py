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

    with ui.left_drawer(value=True, bordered=True).classes("bg-grey-1 p-0 pl-4 pt-4") as drawer:
        drawer.props("width=200")
        with ui.column().classes("gap-1 q-pt-md q-px-sm p-0"):
            with (
                ui.row()
                .classes("items-center gap-2 q-pl-xs cursor-pointer")
                .on("click", lambda: ui.navigate.to("/explorer"))
            ):
                ui.icon("storage").classes("text-grey-7")
                ui.label("Metastore Explorer").classes("text-grey-9 text-body2")

            with (
                ui.row()
                .classes("items-center gap-2 q-pl-xs cursor-pointer")
                .on("click", lambda: ui.navigate.to("/query"))
            ):
                ui.icon("code").classes("text-grey-7")
                ui.label("Query Editor").classes("text-grey-9 text-body2")

            with (
                ui.row()
                .classes("items-center gap-2 q-pl-xs cursor-pointer")
                .on("click", lambda: ui.navigate.to("/jobs"))
            ):
                ui.icon("schedule").classes("text-grey-7")
                ui.label("Jobs").classes("text-grey-9 text-body2")
