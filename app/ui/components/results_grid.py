"""Reusable AG Grid results renderer for SQL query output."""

from nicegui import ui


class ResultsGrid:
    """Renders SQL query results into an AG Grid."""

    def render(self, container: ui.element, result: dict, auto_height: bool = False) -> None:
        """Clear container and render result dict from QueryEngine.execute_typed()."""
        container.clear()
        with container:
            if not result.get("success"):
                with ui.card().classes("w-full bg-red-1 q-pa-md"):
                    ui.label("❌ Query Error").classes("text-h6 text-negative")
                    ui.label(result.get("error", "Unknown error")).classes(
                        "font-mono text-negative"
                    )
                return

            if result.get("message"):
                ui.label(f"✅ {result['message']}").classes("text-positive q-pa-sm")
                return

            columns = result.get("columns", [])
            if not columns:
                ui.label("✅ Query executed (no results).").classes("text-positive q-pa-sm")
                return

            rows = result.get("rows", [])
            ui.label(f"{result['row_count']} row(s) returned").classes(
                "text-caption text-grey q-pa-xs"
            )

            row_number_col = {
                "headerName": "#",
                "valueGetter": "node.rowIndex + 1",
                "width": 60,
                "minWidth": 60,
                "maxWidth": 60,
                "pinned": "left",
                "sortable": False,
                "filter": False,
                "resizable": False,
                "suppressMovable": True,
                "cellStyle": {"color": "#9e9e9e", "textAlign": "right"},
            }
            col_defs = [row_number_col] + [
                {
                    "headerName": f"{col['name']} ({col['type']})",
                    "field": col["name"],
                    "sortable": True,
                    "resizable": True,
                    "filter": True,
                    "minWidth": 120,
                }
                for col in columns
            ]
            col_names = [col["name"] for col in columns]
            row_data = [
                {name: str(val) if val is not None else "" for name, val in zip(col_names, row)}
                for row in rows
            ]
            dom_layout = "autoHeight" if auto_height else "normal"
            many_columns = len(columns) > 5
            grid_style = "width: 100%; overflow-x: auto;" if many_columns else "width: 100%;"
            if not auto_height:
                grid_style += " height: 100%;"
            ui.aggrid(
                options={
                    "columnDefs": col_defs,
                    "rowData": row_data,
                    "domLayout": dom_layout,
                    "defaultColDef": {"sortable": True, "resizable": True, "minWidth": 120},
                    "suppressColumnVirtualisation": False,
                    "rowBuffer": 20,
                },
            ).classes("w-full").style(grid_style)
