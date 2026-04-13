"""Metastore Explorer page."""

from nicegui import ui

from app.services.metastore import manager
from app.services.query import QueryEngine
from app.ui.components.catalog_browser import CatalogBrowser
from app.ui.components.layout import layout_frame
from app.ui.components.results_grid import ResultsGrid


def _render_init_prompt() -> None:
    ui.label("Metastore is not initialized.").classes("text-subtitle1 text-warning")
    init_button = ui.button("Initialize Metastore", icon="play_arrow")
    status_label = ui.label("").classes("text-caption")

    async def do_init():
        try:
            manager.initialize()
            status_label.set_text("✅ Metastore initialized successfully!")
            ui.navigate.to("/explorer")
        except Exception as e:
            status_label.set_text(f"❌ Error: {e}")

    init_button.on_click(do_init)


def _render_detail_panel(detail_container: ui.element, table_path: str) -> None:
    """Render the tabbed detail panel for the selected table/view."""
    detail_container.clear()
    parts = table_path.split(".")
    if len(parts) != 3:
        return
    catalog, schema, table = parts
    query_engine = QueryEngine(manager)
    results_grid = ResultsGrid()

    with detail_container.classes("w-full h-[80vh] border-2 rounded-sm border-grey-3"):
        ui.label(table_path).classes("text-h6 q-pa-md q-pb-xs text-primary")

        with ui.tabs().classes("w-full").props("inline-label") as tabs:
            overview_tab = ui.tab("Overview", icon="info")
            preview_tab = ui.tab("Preview", icon="preview")
            history_tab = ui.tab("History", icon="history")
            properties_tab = ui.tab("Properties", icon="settings")

        with ui.tab_panels(tabs, value="Overview").classes("w-full h-full"):
            with ui.tab_panel(overview_tab):
                comment = manager.get_table_comment(catalog, schema, table)
                if comment:
                    ui.label("Description").classes("text-subtitle2 q-mb-xs")
                    ui.label(comment).classes("text-body2 text-grey-8 q-mb-md")

                view_sql = manager.get_view_definition(catalog, schema, table)
                if view_sql:
                    ui.label("View Definition").classes("text-subtitle2 q-mb-xs")
                    ui.code(view_sql, language="sql").classes("w-full q-mb-md")

                ui.label("Columns").classes("text-subtitle2 q-mb-xs")
                column_search = (
                    ui.input(placeholder="Search columns...")
                    .props("dense clearable")
                    .classes("w-full q-mb-sm")
                )

                describe_result = query_engine.execute_typed(f"DESCRIBE {table_path}")
                if describe_result.get("success") and describe_result.get("rows"):
                    columns_data = describe_result["columns"]
                    rows_data = describe_result["rows"]
                    col_names = [c["name"] for c in columns_data]
                    all_rows = [dict(zip(col_names, r)) for r in rows_data]

                    table_columns = [
                        {
                            "name": c["name"],
                            "label": f"{c['name']} ({c['type']})",
                            "field": c["name"],
                            "align": "left",
                        }
                        for c in columns_data
                    ]

                    col_table = ui.table(
                        columns=table_columns,
                        rows=all_rows,
                        row_key=col_names[0] if col_names else "id",
                    ).classes("w-full")

                    def filter_columns(e) -> None:
                        q = (e.value or "").lower()
                        first_key = col_names[0] if col_names else None
                        filtered = [
                            r
                            for r in all_rows
                            if not q or (first_key and q in str(r.get(first_key, "")).lower())
                        ]
                        col_table.rows = filtered
                        col_table.update()

                    column_search.on_value_change(filter_columns)

            with ui.tab_panel(preview_tab):
                with ui.row().classes("w-full items-center q-mb-sm gap-2"):
                    ui.label("Preview (LIMIT 100)").classes("text-subtitle2 col")
                    ui.button(
                        "Query Table",
                        icon="open_in_new",
                        on_click=lambda: ui.navigate.to(f"/query?table={table_path}"),
                    ).props("dense outline color=primary")
                preview_container = ui.column().classes("w-full")
                with preview_container:
                    ui.label("Select the Preview tab to load data.").classes(
                        "text-caption text-grey q-pa-md"
                    )

            with ui.tab_panel(history_tab):
                history = manager.get_table_history(catalog, schema, table)
                if not history:
                    ui.label("No version history available.").classes(
                        "text-caption text-grey q-pa-md"
                    )
                else:
                    col_names = list(history[0].keys())
                    history_columns = [
                        {
                            "name": c,
                            "label": c.replace("_", " ").title(),
                            "field": c,
                            "align": "left",
                        }
                        for c in col_names
                    ]
                    ui.table(columns=history_columns, rows=history, row_key=col_names[0]).classes(
                        "w-full"
                    )

            with ui.tab_panel(properties_tab):
                props = manager.get_table_properties(catalog, schema, table)
                with ui.list().props("bordered separator").classes("w-full"):
                    for key, value in props.items():
                        with ui.item():
                            with ui.item_section():
                                ui.item_label(key.replace("_", " ").title()).props("overline")
                                ui.item_label(str(value) if value is not None else "N/A")

        preview_loaded = {"done": False}

        def on_tab_change(e) -> None:
            value = e.value
            tab_name = getattr(value, "name", None) or str(value)
            if tab_name == "Preview" and not preview_loaded["done"]:
                preview_loaded["done"] = True
                preview_container.clear()
                preview_result = query_engine.execute_typed(f"SELECT * FROM {table_path} LIMIT 100")
                results_grid.render(preview_container, preview_result, auto_height=True)

        tabs.on_value_change(on_tab_change)


def explorer_page() -> None:
    """Render the Metastore Explorer page."""
    layout_frame()

    ui.query("body").style("overflow: hidden")
    ui.query(".nicegui-content").classes("p-0").style(
        "padding: 0 !important; height: calc(100vh - 64px) !important;"
    )

    if not manager.is_initialized:
        with ui.column().classes("q-pa-lg w-full items-center"):
            _render_init_prompt()
        return

    with (
        ui.splitter(value=25, limits=(15, 50))
        .classes("w-full")
        .style("height: calc(100vh - 64px)") as splitter
    ):
        with splitter.before:
            with ui.column().classes("w-full h-full p-0"):
                ui.label("Catalog Browser").classes("text-subtitle2 q-pa-sm bg-grey-2").style(
                    "margin: 0"
                )
                with ui.scroll_area().classes("w-full").style("flex: 1"):
                    tree_container = ui.column().classes("w-full")

        with splitter.after:
            with ui.scroll_area().classes("w-full h-full"):
                detail_container = ui.column().classes("w-full")
                with detail_container:
                    ui.label("Select a table to view details").classes(
                        "text-subtitle2 text-grey q-pa-md"
                    )

        CatalogBrowser(
            container=tree_container,
            on_table_select=lambda path: _render_detail_panel(detail_container, path),
            metastore=manager,
        )
