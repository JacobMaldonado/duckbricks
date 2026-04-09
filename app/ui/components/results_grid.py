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

            col_defs = [
                {
                    "headerName": f"{col['name']} ({col['type']})",
                    "field": col["name"],
                    "sortable": True,
                    "resizable": True,
                    "filter": True,
                }
                for col in columns
            ]
            col_names = [col["name"] for col in columns]
            row_data = [
                {name: str(val) if val is not None else "" for name, val in zip(col_names, row)}
                for row in rows
            ]
            dom_layout = "autoHeight" if auto_height else "normal"
            grid_style = "width: 100%" if auto_height else "height: 100%"
            ui.aggrid(
                options={
                    "columnDefs": col_defs,
                    "rowData": row_data,
                    "domLayout": dom_layout,
                    "defaultColDef": {"sortable": True, "resizable": True},
                    "suppressColumnVirtualisation": False,
                    "rowBuffer": 20,
                },
            ).classes("w-full").style(grid_style)
