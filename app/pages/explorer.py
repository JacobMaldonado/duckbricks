"""Metastore page with tabbed interface."""
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


def _render_overview_tab(table_name: str, overview_container: ui.column):
    """Render the Overview tab for a table."""
    overview_container.clear()
    table_info = manager.get_table(table_name)
    if table_info is None:
        with overview_container:
            ui.label(f"Table '{table_name}' not found.").classes(
                "text-negative"
            )
        return

    with overview_container:
        # Table header
        ui.label(f"Table: {table_info['name']}").classes(
            "text-h5 q-mb-sm"
        )
        ui.label(
            f"Rows: {table_info['row_count']}"
            f" | Columns: {table_info['column_count']}"
        ).classes("text-caption text-grey q-mb-md")

        # Columns section
        ui.label("Columns").classes("text-h6 q-mb-sm")

        # Create a nice column list with types
        with ui.column().classes("w-full gap-1"):
            for col in table_info.get("columns", []):
                with ui.card().classes("w-full q-pa-sm"):
                    with ui.row().classes("w-full items-center gap-4"):
                        ui.label(col["column_name"]).classes(
                            "text-weight-bold font-mono"
                        ).style("min-width: 200px")
                        ui.badge(col["data_type"]).props(
                            "color=orange text-color=white"
                        )
                        nullable_text = (
                            "Nullable" if col["is_nullable"] == "YES" else "Not Null"
                        )
                        ui.label(nullable_text).classes("text-caption text-grey")


def _render_details_tab(table_name: str, details_container: ui.column):
    """Render the Details tab for a table."""
    details_container.clear()

    try:
        details = manager.get_table_details(table_name)
    except Exception as e:
        with details_container:
            ui.label(f"Error loading details: {e}").classes(
                "text-negative q-pa-md"
            )
        return

    with details_container:
        # Table Statistics
        ui.label("Table Statistics").classes("text-h6 q-mb-md")

        with ui.grid(columns=2).classes("w-full gap-4 q-mb-lg"):
            # Row count card
            with ui.card().classes("q-pa-md"):
                ui.label("Row Count").classes("text-caption text-grey")
                ui.label(str(details["row_count"])).classes(
                    "text-h5 text-primary"
                )

            # File count card
            with ui.card().classes("q-pa-md"):
                ui.label("Number of Files").classes("text-caption text-grey")
                if details["file_count"] > 0:
                    ui.label(str(details["file_count"])).classes(
                        "text-h5 text-primary"
                    )
                else:
                    ui.label("N/A").classes("text-h5 text-grey")

            # Table size card
            with ui.card().classes("q-pa-md"):
                ui.label("Table Size").classes("text-caption text-grey")
                if details["table_size_bytes"] > 0:
                    size_gb = details["table_size_bytes"] / (1024**3)
                    ui.label(f"{size_gb:.2f} GB").classes(
                        "text-h5 text-primary"
                    )
                else:
                    ui.label("N/A").classes("text-h5 text-grey")

            # Last modified card
            with ui.card().classes("q-pa-md"):
                ui.label("Last Modified").classes("text-caption text-grey")
                if details["last_modified"]:
                    ui.label(details["last_modified"]).classes(
                        "text-h6 text-primary"
                    )
                else:
                    ui.label("Unknown").classes("text-h6 text-grey")

        # Partitioning info
        if details["partitions"]:
            ui.label("Partitioning").classes("text-h6 q-mb-sm")
            with ui.card().classes("w-full q-pa-md bg-orange-1"):
                for partition in details["partitions"]:
                    ui.label(f"• {partition}").classes("text-body2")

        # Constraints
        if details["constraints"]:
            ui.label("Constraints").classes("text-h6 q-mt-md q-mb-sm")
            for constraint in details["constraints"]:
                with ui.card().classes("w-full q-pa-sm q-mb-xs bg-blue-1"):
                    ui.label(constraint["type"]).classes(
                        "text-weight-bold text-caption"
                    )
                    if constraint.get("definition"):
                        ui.label(constraint["definition"]).classes(
                            "text-caption font-mono"
                        )

        # Show placeholder message if no advanced data
        if (not details["partitions"]
            and not details["constraints"]
            and details["file_count"] == 0
            and details["table_size_bytes"] == 0):
            ui.label(
                "Advanced metadata not yet available. "
                "This feature requires additional DuckLake metadata integration."
            ).classes("text-caption text-grey q-mt-md")


def _render_history_tab(table_name: str, history_container: ui.column):
    """Render the History tab for a table."""
    history_container.clear()

    try:
        history = manager.get_table_history(table_name)
    except Exception as e:
        with history_container:
            ui.label(f"Error loading history: {e}").classes(
                "text-negative q-pa-md"
            )
        return

    with history_container:
        ui.label("Time Travel Snapshots").classes("text-h6 q-mb-md")

        if not history:
            ui.label(
                "No version history available. "
                "This feature requires DuckLake versioning to be configured."
            ).classes("text-caption text-grey q-pa-md")
            return

        # Render version history
        for version in history:
            with ui.card().classes("w-full q-mb-sm"):
                with ui.row().classes(
                    "w-full items-center justify-between q-pa-sm"
                ):
                    with ui.column():
                        ui.label(version["version_id"]).classes(
                            "text-weight-bold font-mono"
                        )
                        ui.label(version["timestamp"]).classes(
                            "text-caption text-grey"
                        )
                    if version["is_current"]:
                        ui.badge("Current").props("color=positive")


def explorer_page():
    """Render the Metastore page with tabbed interface."""
    layout_frame()

    # Disable outer scrolling for consistent layout
    ui.query("body").style("overflow: hidden")
    ui.query(".nicegui-content").classes("p-0").style(
        "padding: 0 !important; "
        "height: calc(100vh - 64px) !important;"
    )

    if not manager.is_initialized:
        with ui.column().classes("q-pa-lg w-full items-center"):
            _render_init_prompt()
        return

    try:
        tables = manager.list_tables()
    except Exception as e:
        with ui.column().classes("q-pa-lg w-full"):
            ui.label(f"Error loading tables: {e}").classes(
                "text-negative"
            )
        return

    if not tables:
        with ui.column().classes("q-pa-lg w-full"):
            _render_empty_state()
        return

    # Two-panel layout: left=table list, right=tabbed details
    with ui.splitter(value=25, limits=(15, 50)).classes("w-full").style(
        "height: calc(100vh - 64px)"
    ) as splitter:

        # LEFT PANEL: Table List
        with splitter.before:
            with ui.column().classes("w-full h-full p-0"):
                ui.label("Tables").classes(
                    "text-subtitle2 q-pa-sm bg-grey-2"
                ).style("margin: 0")
                ui.label(f"{len(tables)} table(s)").classes(
                    "text-caption text-grey q-pa-xs q-pl-sm"
                )

                # Container for table selection
                selected_table = {"name": None}

                with ui.scroll_area().classes("w-full").style("flex: 1"):
                    # Table list
                    for t in tables:
                        table_name = t['name']

                        def make_handler(name):
                            def handler():
                                selected_table["name"] = name
                                _render_overview_tab(name, overview_container)
                                _render_details_tab(name, details_container)
                                _render_history_tab(name, history_container)
                            return handler

                        ui.button(
                            f"📋 {table_name}",
                            on_click=make_handler(table_name),
                        ).classes("w-full q-mb-xs").props(
                            "flat align=left no-caps"
                        )

        # RIGHT PANEL: Tabbed Interface
        with splitter.after:
            with ui.column().classes("w-full h-full p-0"):
                # Tabs
                with ui.tabs().classes("w-full") as tabs:
                    overview_tab = ui.tab("Overview")
                    details_tab = ui.tab("Details")
                    history_tab = ui.tab("History")

                # Tab Panels
                with ui.tab_panels(
                    tabs, value=overview_tab
                ).classes("w-full").style("flex: 1; overflow-y: auto"):

                    # OVERVIEW TAB
                    with ui.tab_panel(overview_tab):
                        overview_container = ui.column().classes("w-full q-pa-md")
                        with overview_container:
                            ui.label(
                                "Select a table from the list to view details"
                            ).classes("text-subtitle2 text-grey")

                    # DETAILS TAB
                    with ui.tab_panel(details_tab):
                        details_container = ui.column().classes("w-full q-pa-md")
                        with details_container:
                            ui.label(
                                "Select a table from the list to view details"
                            ).classes("text-subtitle2 text-grey")

                    # HISTORY TAB
                    with ui.tab_panel(history_tab):
                        history_container = ui.column().classes("w-full q-pa-md")
                        with history_container:
                            ui.label(
                                "Select a table from the list to view history"
                            ).classes("text-subtitle2 text-grey")
