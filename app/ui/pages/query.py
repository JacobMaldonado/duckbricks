"""Query Workspace page — IDE-like SQL editor with catalog browser."""

import time

from nicegui import ui

from app.services.metastore import manager
from app.services.query import QueryEngine
from app.ui.components.catalog_browser import render_hierarchy_tree
from app.ui.components.layout import layout_frame
from app.ui.components.results_grid import ResultsGrid


def _find_node(nodes: list[dict], node_id: str) -> dict | None:
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


def _build_catalog_tree() -> ui.tree:
    """Build the catalog hierarchy tree with lazy loading."""

    def load_tree_nodes() -> list[dict]:
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
    tree = ui.tree(
        nodes=nodes,
        node_key="id",
        label_key="label",
    ).classes("w-full")

    async def on_expand(e):
        expanded_ids = e.value if isinstance(e.value, set) else {e.value}

        for node_id in expanded_ids:
            node = _find_node(tree._props["nodes"], node_id)
            if node is None:
                continue
            if node.get("children") and node["children"][0].get("id") != "__loading__":
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
                    tables = manager.list_tables_in_schema(catalog, schema)
                    node["children"] = [
                        {
                            "id": (f"{catalog}.{schema}.{table}"),
                            "label": f"📋 {table}",
                        }
                        for table in tables
                    ]
            except Exception:
                node["children"] = []

        tree.update()

    tree.on("expand", on_expand)
    return tree


def _render_results(results_container, result: dict):
    """Render query results using AG Grid with typed headers."""
    ResultsGrid().render(results_container, result)


def query_workspace():
    """Render the Query Workspace page."""
    layout_frame()

    ui.query("body").style("overflow: hidden")
    ui.query(".nicegui-content").classes("p-0").style(
        "padding: 0 !important; height: calc(100vh - 64px) !important;"
    )
    ui.add_head_html("""
    <style>
    .cm-editor .cm-tooltip-autocomplete {
        z-index: 9999 !important;
    }
    .cm-editor { overflow: visible !important; }
    </style>
    """)

    table_param = ui.context.client.request.query_params.get("table")
    initial_sql = (
        f"SELECT *\nFROM {table_param}\nLIMIT 100"
        if table_param
        else "-- Write your SQL query here\n"
    )

    if not manager.is_initialized:
        with ui.column().classes("q-pa-lg w-full items-center"):
            ui.label("Metastore is not initialized.").classes("text-h5 text-warning")
            status_label = ui.label("").classes("text-caption")

            async def do_init():
                try:
                    manager.initialize()
                    status_label.set_text("✅ Initialized!")
                    ui.navigate.to("/query")
                except Exception as e:
                    status_label.set_text(f"❌ Error: {e}")

            ui.button("Initialize Metastore", icon="play_arrow", on_click=do_init)
        return

    query_engine = QueryEngine(manager)
    results_grid = ResultsGrid()

    with (
        ui.splitter(value=20, limits=(10, 40))
        .classes("w-full")
        .style("height: calc(100vh - 64px)") as h_splitter
    ):
        with h_splitter.before:
            with ui.column().classes("w-full h-full p-0"):
                ui.label("Catalog Browser").classes("text-subtitle2 q-pa-sm bg-grey-2").style(
                    "margin: 0"
                )
                with ui.scroll_area().classes("w-full").style("flex: 1"):
                    tree_container = ui.column().classes("w-full")

        with h_splitter.after:
            with ui.splitter(
                horizontal=True,
                value=40,
                limits=(15, 85),
            ).classes("w-full h-full") as v_splitter:
                with v_splitter.before:
                    with ui.column().classes("w-full h-full p-0 gap-0"):
                        with (
                            ui.row()
                            .classes("w-full items-center q-pa-xs bg-grey-1 gap-2")
                            .style("flex-shrink: 0")
                        ):
                            execute_btn = (
                                ui.button("Execute", icon="play_arrow")
                                .props("color=primary dense")
                                .tooltip("Shift+Enter")
                            )
                            status_label = ui.label("").classes("text-caption text-grey")

                        editor = (
                            ui.codemirror(
                                value=initial_sql,
                                language="SQL",
                                theme="githubLight",
                            )
                            .classes("w-full")
                            .style("flex: 1; overflow: visible")
                        )

                        _editor_id = editor.id
                        _cache_bust = int(time.time())
                        ui.run_javascript(
                            f"import('/static/sql_completion.js?v={_cache_bust}')"
                            f".then(m => m.mount({_editor_id}, {{"
                            f"  onExecute: () => emitEvent('execute-query')"
                            f"}}))"
                            f".catch(e => console.error('[sql_completion]', e))"
                        )

                with v_splitter.after:
                    results_container = ui.column().classes("w-full h-full p-0 gap-0")
                    with results_container:
                        ui.label("Results will appear here").classes(
                            "text-caption text-grey q-pa-md"
                        )

                async def run_query():
                    selected = await ui.run_javascript(f"""
                        (() => {{
                            const comp = getElement({_editor_id});
                            if (!comp || !comp.editor) return '';
                            const state = comp.editor.state;
                            const sel = state.selection.main;
                            return sel.empty ? '' : state.sliceDoc(sel.from, sel.to);
                        }})();
                    """)
                    sql = selected.strip() if selected and selected.strip() else editor.value
                    if not sql or not sql.strip():
                        ui.notify("Please enter a SQL query.", type="warning")
                        return

                    execute_btn.disable()
                    status_label.set_text("⏳ Running...")

                    try:
                        result = query_engine.execute_typed(sql.strip())
                        results_grid.render(results_container, result)
                        if result.get("success"):
                            status_label.set_text(f"✅ {result.get('row_count', 0)} rows")
                        else:
                            status_label.set_text("❌ Error")
                    except Exception as e:
                        results_container.clear()
                        with results_container:
                            ui.label(f"❌ {e}").classes("text-negative q-pa-md")
                        status_label.set_text("❌ Error")
                    finally:
                        execute_btn.enable()

                execute_btn.on_click(run_query)
                ui.on("execute-query", lambda _: run_query())

                def insert_into_editor(path: str) -> None:
                    editor_id = editor.id
                    ui.run_javascript(f"""
                        (function() {{
                            const comp = getElement({editor_id});
                            if (!comp || !comp.editor) return;
                            const view = comp.editor;
                            view.dispatch(view.state.replaceSelection(' {path} '));
                            view.focus();
                        }})();
                    """)

                ui.run_javascript("""
                    const editorEl = document.querySelector('.cm-editor');
                    if (editorEl) {
                        editorEl.addEventListener('dragover', e => e.preventDefault());
                        editorEl.addEventListener('drop', e => {
                            e.preventDefault();
                            const path = e.dataTransfer.getData('text/plain');
                            if (path && !path.startsWith('__')) {
                                emitEvent('editor-drop', path);
                            }
                        });
                    }
                """)
                ui.on("editor-drop", lambda e: insert_into_editor(e.args))

        render_hierarchy_tree(
            tree_container,
            on_insert_to_editor=insert_into_editor,
        )
