"""Query Workspace page — IDE-like SQL editor with catalog browser."""
from nicegui import ui

from app.components.layout import layout_frame
from app.services.ducklake import manager


def _build_catalog_tree(on_insert_path=None) -> ui.tree:
    """Build the catalog hierarchy tree with lazy loading.

    Args:
        on_insert_path: Optional callback(table_path: str) for inserting table paths.
    """

    def load_tree_nodes() -> list[dict]:
        """Load top-level catalog nodes."""
        if not manager.is_initialized:
            return []
        try:
            catalogs = manager.list_catalogs()
            return [
                {
                    "id": cat,
                    "label": f"📁 {cat}",
                    "children": [],
                }
                for cat in catalogs
            ]
        except Exception:
            return []

    nodes = load_tree_nodes()

    # Add custom styling for insert icons
    ui.add_head_html("""
    <style>
        .insert-icon {
            opacity: 0;
            transition: opacity 0.2s;
            margin-left: 4px;
        }
        .tree-node-row:hover .insert-icon {
            opacity: 1;
        }
    </style>
    """)

    tree = ui.tree(
        nodes=nodes,
        node_key="id",
        label_key="label",
    ).classes("w-full")

    async def on_expand(e):
        """Lazy-load children when a node is expanded."""
        expanded_ids = (
            e.value if isinstance(e.value, set) else {e.value}
        )

        for node_id in expanded_ids:
            node = _find_node(tree._props["nodes"], node_id)
            if node is None:
                continue
            # Skip if children already loaded
            if node.get("children") and node["children"][0].get(
                "id"
            ) != "__loading__":
                continue

            parts = node_id.split(".")
            try:
                if len(parts) == 1:
                    catalog = parts[0]
                    schemas = manager.list_schemas(catalog)
                    node["children"] = [
                        {
                            "id": f"{catalog}.{schema}",
                            "label": f"📂 {schema}",
                            "children": [],
                        }
                        for schema in schemas
                    ]
                elif len(parts) == 2:
                    catalog, schema = parts
                    tables = (
                        manager.list_tables_in_schema(
                            catalog, schema
                        )
                    )
                    # For table nodes, add a marker to render insert button
                    node["children"] = [
                        {
                            "id": (
                                f"{catalog}.{schema}.{table}"
                            ),
                            "label": f"📋 {table}",
                            "_is_table": True,
                        }
                        for table in tables
                    ]
            except Exception:
                node["children"] = []

        tree.update()

    tree.on("expand", on_expand)

    # Add click handler for insert action
    if on_insert_path:
        def on_select(e):
            """Handle table node selection for path insertion."""
            selected_id = e.value
            if selected_id and "." in selected_id:
                parts = selected_id.split(".")
                if len(parts) == 3:  # It's a table
                    on_insert_path(selected_id)

        tree.on("dblclick", on_select)

    return tree


def _find_node(
    nodes: list[dict], node_id: str
) -> dict | None:
    """Recursively find a node by ID in the tree."""
    for node in nodes:
        if node["id"] == node_id:
            return node
        children = node.get("children", [])
        if children:
            found = _find_node(children, node_id)
            if found:
                return found
    return None


def _render_results(results_container, result: dict, sql_query: str = ""):
    """Render query results using AG Grid with typed headers.

    Args:
        results_container: Container to render results in
        result: Query result dict
        sql_query: Original SQL query for export functionality
    """
    results_container.clear()
    with results_container:
        if not result.get("success"):
            with ui.card().classes("w-full bg-red-1 q-pa-md"):
                ui.label("❌ Query Error").classes(
                    "text-h6 text-negative"
                )
                ui.label(
                    result.get("error", "Unknown error")
                ).classes("font-mono text-negative")
            return

        if result.get("message"):
            ui.label(f"✅ {result['message']}").classes(
                "text-positive q-pa-sm"
            )
            return

        columns = result.get("columns", [])
        if not columns:
            ui.label(
                "✅ Query executed (no results)."
            ).classes("text-positive q-pa-sm")
            return

        rows = result.get("rows", [])

        # Header with row count and export button
        with ui.row().classes("w-full items-center justify-between q-pa-xs"):
            ui.label(
                f"{result['row_count']} row(s) returned"
            ).classes("text-caption text-grey")

            # Export button
            def export_to_csv():
                """Export current results to CSV."""
                try:
                    csv_data = manager.export_results_to_csv(sql_query)
                    # Create download using NiceGUI
                    import base64
                    b64_data = base64.b64encode(csv_data).decode()
                    ui.download(
                        f"data:text/csv;base64,{b64_data}",
                        "query_results.csv"
                    )
                    ui.notify("CSV export started", type="positive")
                except Exception as e:
                    ui.notify(f"Export failed: {str(e)}", type="negative")

            ui.button(
                "📥 Export to CSV",
                on_click=export_to_csv,
            ).props("color=primary outlined dense")

        # AG Grid column defs with typed headers
        col_defs = [
            {
                "headerName": (
                    f"{col['name']} ({col['type']})"
                ),
                "field": col["name"],
                "sortable": True,
                "resizable": True,
                "filter": True,
            }
            for col in columns
        ]

        col_names = [col["name"] for col in columns]
        row_data = [
            {
                name: str(val) if val is not None else ""
                for name, val in zip(col_names, row)
            }
            for row in rows
        ]

        ui.aggrid(
            options={
                "columnDefs": col_defs,
                "rowData": row_data,
                "domLayout": "normal",
                "defaultColDef": {
                    "sortable": True,
                    "resizable": True,
                },
                "suppressColumnVirtualisation": False,
                "rowBuffer": 20,
            },
        ).classes("w-full").style("height: 100%")


def query_workspace():
    """Render the Query Workspace page."""
    layout_frame()

    # Disable outer scrolling for IDE-like experience
    ui.query("body").style("overflow: hidden")
    ui.query(".nicegui-content").classes("p-0").style(
        "padding: 0 !important; "
        "height: calc(100vh - 64px) !important;"
    )

    if not manager.is_initialized:
        with ui.column().classes(
            "q-pa-lg w-full items-center"
        ):
            ui.label(
                "Metastore is not initialized."
            ).classes("text-h5 text-warning")
            status_label = ui.label("").classes(
                "text-caption"
            )

            async def do_init():
                try:
                    manager.initialize()
                    status_label.set_text("✅ Initialized!")
                    ui.navigate.to("/query")
                except Exception as e:
                    status_label.set_text(f"❌ Error: {e}")

            ui.button(
                "Initialize Metastore",
                icon="play_arrow",
                on_click=do_init,
            )
        return

    # Horizontal splitter: left=tree | right=editor+results
    with ui.splitter(
        value=20, limits=(10, 40)
    ).classes("w-full").style(
        "height: calc(100vh - 64px)"
    ) as h_splitter:

        # === LEFT PANEL: Catalog Tree ===
        with h_splitter.before:
            with ui.column().classes("w-full h-full p-0"):
                ui.label("Catalog Browser").classes(
                    "text-subtitle2 q-pa-sm bg-grey-2"
                ).style("margin: 0")
                ui.label("Double-click table to insert").classes(
                    "text-caption text-grey q-pa-xs"
                )
                with ui.scroll_area().classes(
                    "w-full"
                ).style("flex: 1"):
                    # Will be populated after editor is created
                    tree_placeholder = ui.column().classes("w-full")

        # === RIGHT PANEL: Editor + Results ===
        with h_splitter.after:
            with ui.splitter(
                horizontal=True,
                value=40,
                limits=(15, 85),
            ).classes(
                "w-full h-full"
            ) as v_splitter:

                # --- TOP: SQL Editor ---
                with v_splitter.before:
                    with ui.column().classes(
                        "w-full h-full p-0 gap-0"
                    ):
                        with ui.row().classes(
                            "w-full items-center "
                            "q-pa-xs bg-grey-1 gap-2"
                        ).style("flex-shrink: 0"):
                            execute_btn = ui.button(
                                "▶ Execute",
                                icon="play_arrow",
                            ).props("color=primary dense")
                            status_label = ui.label(
                                ""
                            ).classes(
                                "text-caption text-grey"
                            )
                            ui.space()

                            # Table search/autocomplete
                            search_input = ui.input(
                                placeholder="Search tables...",
                            ).props("dense outlined").classes("q-mr-sm").style(
                                "width: 250px"
                            )

                        # Autocomplete dropdown container
                        autocomplete_container = ui.column().classes(
                            "w-full"
                        ).style("position: relative; height: 0; z-index: 1000")

                        editor = ui.codemirror(
                            value=(
                                "-- Write your SQL "
                                "query here\n"
                            ),
                            language="SQL",
                            theme="githubLight",
                        ).classes("w-full").style(
                            "flex: 1; overflow: auto"
                        )

                        # Define insert handler
                        def insert_table_path(table_path: str):
                            """Insert table path into editor at cursor position."""
                            current = editor.value or ""
                            # Insert at end with a space for now
                            # (cursor position tracking is complex in CodeMirror)
                            if current and not current.endswith(" "):
                                editor.value = f"{current} {table_path} "
                            else:
                                editor.value = f"{current}{table_path} "
                            editor.update()
                            ui.notify(f"Inserted: {table_path}", type="positive")

                        # Autocomplete functionality
                        def show_autocomplete_results(search_query: str):
                            """Show autocomplete dropdown with matching tables."""
                            autocomplete_container.clear()

                            if not search_query or len(search_query) < 2:
                                return

                            try:
                                results = manager.search_tables(search_query)

                                if results:
                                    with autocomplete_container:
                                        with ui.card().classes(
                                            "absolute bg-white"
                                        ).style(
                                            "top: 0; right: 10px; "
                                            "max-width: 400px; "
                                            "max-height: 300px; "
                                            "overflow-y: auto; "
                                            "box-shadow: 0 4px 12px rgba(0,0,0,0.15)"
                                        ):
                                            ui.label(
                                                f"{len(results)} table(s) found"
                                            ).classes("text-caption text-grey q-pa-xs")

                                            for result in results:
                                                def make_insert_handler(full_name):
                                                    def handler():
                                                        insert_table_path(full_name)
                                                        autocomplete_container.clear()
                                                        search_input.value = ""
                                                    return handler

                                                with ui.row().classes(
                                                    "w-full items-center gap-2 cursor-pointer"
                                                ).on(
                                                    "click",
                                                    make_insert_handler(result["full_name"])
                                                ).style(
                                                    "padding: 8px; "
                                                    "border-bottom: 1px solid #f0f0f0"
                                                ):
                                                    ui.label(
                                                        result["full_name"]
                                                    ).classes("font-mono text-sm")
                                                    ui.badge(
                                                        f"{result['column_count']} cols"
                                                    ).props("color=grey")
                            except Exception:
                                # Silently fail to avoid disrupting the UI
                                pass

                        # Wire up search input
                        search_input.on(
                            "update:model-value",
                            lambda e: show_autocomplete_results(e.args)
                        )

                        # Clear autocomplete when clicking outside
                        def clear_autocomplete():
                            autocomplete_container.clear()

                        editor.on("focus", clear_autocomplete)

                        # Build tree with insert handler
                        with tree_placeholder:
                            _build_catalog_tree(on_insert_path=insert_table_path)

                # --- BOTTOM: Results ---
                with v_splitter.after:
                    results_container = ui.column().classes(
                        "w-full h-full p-0 gap-0"
                    )
                    with results_container:
                        ui.label(
                            "Results will appear here"
                        ).classes(
                            "text-caption text-grey q-pa-md"
                        )

                # --- Execute handler ---
                async def run_query():
                    sql = editor.value
                    if not sql or not sql.strip():
                        ui.notify(
                            "Please enter a SQL query.",
                            type="warning",
                        )
                        return

                    execute_btn.disable()
                    status_label.set_text("⏳ Running...")

                    try:
                        sql_stripped = sql.strip()
                        result = (
                            manager.execute_query_typed(
                                sql_stripped
                            )
                        )
                        _render_results(
                            results_container, result, sql_stripped
                        )
                        if result.get("success"):
                            status_label.set_text(
                                f"✅ "
                                f"{result.get('row_count', 0)}"
                                f" rows"
                            )
                        else:
                            status_label.set_text(
                                "❌ Error"
                            )
                    except Exception as e:
                        results_container.clear()
                        with results_container:
                            ui.label(f"❌ {e}").classes(
                                "text-negative q-pa-md"
                            )
                        status_label.set_text("❌ Error")
                    finally:
                        execute_btn.enable()

                execute_btn.on_click(run_query)
