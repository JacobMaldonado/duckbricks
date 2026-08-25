"""DuckLake-backed Metastore Workbench page."""

import traceback

from nicegui import ui

from app.services.metastore import manager
from app.services.metastore.asset_service import MetastoreAssetService
from app.ui.components.layout import layout_frame
from app.ui.components.metastore_workbench import MetastoreWorkbench


def _render_init_prompt() -> None:
    ui.label("Metastore is not initialized.").classes("text-subtitle1 text-warning")
    init_button = ui.button("Initialize Metastore", icon="play_arrow")
    status_label = ui.label("").classes("text-caption")

    async def do_init() -> None:
        try:
            manager.initialize()
            status_label.set_text("Metastore initialized successfully.")
            ui.navigate.to("/explorer")
        except Exception as exc:
            status_label.set_text(f"Error: {exc}")
            traceback.print_exc()

    init_button.on_click(do_init)


def explorer_page() -> None:
    """Render the selected three-pane Metastore Workbench."""
    layout_frame("Metastore Workbench")

    if not manager.is_initialized:
        with ui.column().classes("q-pa-lg w-full items-center"):
            _render_init_prompt()
        return

    MetastoreWorkbench(MetastoreAssetService(manager)).render()
