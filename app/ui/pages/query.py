"""Query Workspace page — IDE-like SQL editor with catalog browser and persistent tabs."""

import time

from nicegui import ui

from app.services.metastore import manager
from app.services.query import QueryEngine, QueryTabService
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
    .query-tab-bar { border-bottom: 1px solid #e0e0e0; }
    .query-tab-chip { cursor: pointer; user-select: none; }
    .query-tab-chip.active { background: #1976d2 !important; color: white !important; }
    .query-tab-chip .close-btn { opacity: 0.6; }
    .query-tab-chip .close-btn:hover { opacity: 1; }
    .query-tab-rename-input { font-size: 13px; border: none; outline: none;
        background: transparent; color: inherit; width: 120px; }
    </style>
    """)

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
    tab_service = QueryTabService()

    all_tabs = tab_service.list_tabs()
    if not all_tabs:
        tab_service.ensure_default()
        all_tabs = tab_service.list_tabs()

    active_tab_id: list[int] = [all_tabs[0].id]
    _add_tab_holder: list = [None]

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
                            .classes("w-full items-center q-pa-xs bg-grey-1 gap-2 query-tab-bar")
                            .style("flex-shrink: 0; flex-wrap: nowrap; overflow-x: auto;")
                        ):
                            execute_btn = (
                                ui.button("Execute", icon="play_arrow")
                                .props("color=primary dense")
                                .tooltip("Shift+Enter")
                            )
                            status_label = ui.label("").classes("text-caption text-grey")
                            tab_bar_row = (
                                ui.row()
                                .classes("items-center gap-1")
                                .style("flex-wrap: nowrap; overflow-x: auto;")
                            )
                            ui.button(icon="add", on_click=lambda: _add_tab_holder[0]()).props(
                                "flat dense round size=sm"
                            ).tooltip("New tab")

                        initial_tab = all_tabs[0]
                        editor = (
                            ui.codemirror(
                                value=initial_tab.sql_content or "-- Write your SQL query here\n",
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

    _build_tab_bar(tab_bar_row, all_tabs, active_tab_id, editor, tab_service, _add_tab_holder)


def _build_tab_bar(
    container,
    initial_tabs,
    active_tab_id: list[int],
    editor,
    tab_service: QueryTabService,
    add_tab_holder: list,
) -> None:
    """Render the tab bar chips and wire all tab interactions.

    The caller is responsible for providing ``add_tab_holder``, a single-element
    list that will be populated with the ``_add_tab`` callable so external UI
    elements (e.g. a toolbar button) can trigger new-tab creation.
    """
    tab_chips: dict[int, ui.element] = {}

    def _save_active_content() -> None:
        try:
            tab_service.update_content(active_tab_id[0], editor.value)
        except Exception:
            pass

    def _activate_tab(tab_id: int) -> None:
        _save_active_content()
        active_tab_id[0] = tab_id
        _refresh_chip_styles()
        tab = next((t for t in tab_service.list_tabs() if t.id == tab_id), None)
        if tab is not None:
            editor.set_value(tab.sql_content or "")

    def _refresh_chip_styles() -> None:
        for tid, chip in tab_chips.items():
            if tid == active_tab_id[0]:
                chip.classes(add="active")
            else:
                chip.classes(remove="active")

    def _close_tab(tab_id: int) -> None:
        _save_active_content()
        try:
            tab_service.delete_tab(tab_id)
        except ValueError as exc:
            ui.notify(str(exc), type="warning")
            return

        if tab_id in tab_chips:
            tab_chips[tab_id].delete()
            del tab_chips[tab_id]

        if active_tab_id[0] == tab_id and tab_chips:
            next_id = next(iter(tab_chips))
            _activate_tab(next_id)

    def _add_tab() -> None:
        existing = tab_service.list_tabs()
        name = f"Query {len(existing) + 1}"
        new_tab = tab_service.create_tab(name)
        _render_tab_chip(new_tab.id, new_tab.name)
        _activate_tab(new_tab.id)

    add_tab_holder[0] = _add_tab

    def _render_tab_chip(tab_id: int, tab_name: str) -> None:
        with container:
            with (
                ui.element("div")
                .classes("query-tab-chip row items-center q-px-sm q-py-xs rounded-borders gap-1")
                .style("background: #f5f5f5; border: 1px solid #ddd; min-width: 80px;") as chip
            ):
                tab_chips[tab_id] = chip

                label_el = (
                    ui.label(tab_name).classes("text-caption").style("cursor: pointer; flex: 1")
                )
                rename_input = (
                    ui.input(value=tab_name)
                    .classes("query-tab-rename-input")
                    .style("display: none; flex: 1")
                )

                def _start_rename(tid: int = tab_id, lbl=label_el, inp=rename_input) -> None:
                    lbl.style("display: none")
                    inp.style("display: inline-block")
                    inp.run_method("focus")

                def _commit_rename(tid: int = tab_id, lbl=label_el, inp=rename_input) -> None:
                    new_name = inp.value.strip() or lbl.text
                    try:
                        tab_service.rename_tab(tid, new_name)
                        lbl.set_text(new_name)
                    except ValueError as exc:
                        ui.notify(str(exc), type="warning")
                    inp.style("display: none")
                    lbl.style("display: inline-block")

                label_el.on("dblclick", lambda _, tid=tab_id: _start_rename(tid))
                rename_input.on("blur", lambda _, tid=tab_id: _commit_rename(tid))
                rename_input.on("keydown.enter", lambda _, tid=tab_id: _commit_rename(tid))
                rename_input.on(
                    "keydown.escape",
                    lambda _, lbl=label_el, inp=rename_input: (
                        inp.style("display: none"),
                        lbl.style("display: inline-block"),
                    ),
                )

                chip.on("click", lambda _, tid=tab_id: _activate_tab(tid))

                ui.button(icon="close", on_click=lambda _, tid=tab_id: _close_tab(tid)).props(
                    "flat dense round size=xs"
                ).classes("close-btn")

        if tab_id == active_tab_id[0]:
            tab_chips[tab_id].classes(add="active")

    for tab in initial_tabs:
        _render_tab_chip(tab.id, tab.name)
