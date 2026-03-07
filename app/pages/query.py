"""Execution Environment page."""
from nicegui import ui

from app.components.layout import layout_frame
from app.services.ducklake import manager


def _render_init_prompt():
    """Render initialization prompt when metastore is not ready."""
    ui.label("Metastore is not initialized.").classes(
        "text-subtitle1 text-warning"
    )
    status_label = ui.label("").classes("text-caption")

    async def do_init():
        try:
            manager.initialize()
            status_label.set_text("✅ Initialized!")
            ui.navigate.to("/query")
        except Exception as e:
            status_label.set_text(f"❌ Error: {e}")

    ui.button(
        "Initialize Metastore", icon="play_arrow", on_click=do_init
    )


def _render_results(results_container: ui.column, result: dict):
    """Render query results into the container."""
    results_container.clear()
    with results_container:
        if not result.get("success"):
            with ui.card().classes("w-full bg-red-1"):
                ui.label("❌ Query Error").classes(
                    "text-h6 text-negative"
                )
                ui.label(
                    result.get("error", "Unknown error")
                ).classes("text-body1 font-mono text-negative")
            return

        if result.get("message"):
            ui.label(f"✅ {result['message']}").classes(
                "text-positive"
            )
            return

        if not result.get("columns"):
            ui.label(
                "✅ Query executed successfully (no results)."
            ).classes("text-positive")
            return

        ui.label(
            f"✅ {result['row_count']} row(s) returned"
        ).classes("text-caption text-grey q-mb-sm")

        columns = [
            {
                "name": col,
                "label": col,
                "field": col,
                "align": "left",
                "sortable": True,
            }
            for col in result["columns"]
        ]
        rows = [
            {
                col: str(val)
                for col, val in zip(result["columns"], row)
            }
            for row in result["rows"]
        ]
        ui.table(
            columns=columns,
            rows=rows,
            row_key=result["columns"][0],
            pagination={"rowsPerPage": 25},
        ).classes("w-full")


def query_page():
    """Render the SQL Query Editor page."""
    layout_frame()

    with ui.column().classes("q-pa-lg w-full"):
        ui.label("Query Editor").classes("text-h4 q-mb-md")

        if not manager.is_initialized:
            _render_init_prompt()
            return

        ui.label("Write your SQL query below:").classes(
            "text-subtitle2 q-mb-sm"
        )
        sql_input = ui.textarea(
            placeholder="SELECT * FROM my_table LIMIT 10;",
        ).classes("w-full font-mono").props(
            "outlined autogrow rows=6"
        )

        results_container = ui.column().classes("w-full q-mt-md")

        async def execute_query():
            sql = sql_input.value
            if not sql or not sql.strip():
                ui.notify(
                    "Please enter a SQL query.", type="warning"
                )
                return

            results_container.clear()
            with results_container:
                ui.spinner("dots", size="lg")

            result = manager.execute_query(sql.strip())
            _render_results(results_container, result)

        ui.button(
            "▶ Execute",
            on_click=execute_query,
            icon="play_arrow",
        ).classes("q-mt-sm").props("color=primary")
