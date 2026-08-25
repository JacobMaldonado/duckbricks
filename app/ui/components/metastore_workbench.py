"""Three-pane Metastore Workbench backed by live DuckLake metadata."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from urllib.parse import quote

from nicegui import ui

from app.services.metastore.asset_service import (
    AssetListItem,
    AssetMetadata,
    AssetPath,
    MetastoreAssetService,
)
from app.ui.components.catalog_browser import CatalogBrowser
from app.ui.components.results_grid import ResultsGrid

QUALITY_ICON = "verified"

METASTORE_WORKBENCH_CSS = """
<style>
.metastore-workbench-page {
    background: #fafafa;
    height: calc(100vh - 64px);
    overflow: hidden;
}
.metastore-workbench-shell {
    display: grid;
    grid-template-columns: 250px 310px minmax(0, 1fr);
    flex: 1;
    min-height: 0;
}
.metastore-workbench-pane {
    background: white;
    min-height: 0;
    overflow: hidden;
}
.metastore-workbench-pane + .metastore-workbench-pane {
    border-left: 1px solid #e0e0e0;
}
.metastore-workbench-scroll {
    height: 100%;
    overflow-y: auto;
}
.metastore-workbench-asset {
    cursor: pointer;
    border: 1px solid transparent;
    transition: background-color 120ms ease, border-color 120ms ease;
}
.metastore-workbench-asset:hover { background: #f5f5f5; }
.metastore-workbench-asset.selected {
    background: #e3f2fd;
    border-color: #90caf9;
}
.metastore-workbench-metric { min-width: 155px; }
.metastore-workbench-metric-icon {
    align-items: center;
    display: inline-flex;
    flex: 0 0 24px;
    height: 24px;
    justify-content: center;
    line-height: 1;
    width: 24px;
}
@media (max-width: 1100px) {
    .metastore-workbench-shell { grid-template-columns: 220px 260px minmax(0, 1fr); }
}
@media (max-width: 850px) {
    .metastore-workbench-page { height: auto; min-height: calc(100vh - 64px); overflow: auto; }
    .metastore-workbench-shell { display: flex; flex-direction: column; }
    .metastore-workbench-pane { min-height: 280px; overflow: visible; }
    .metastore-workbench-pane + .metastore-workbench-pane {
        border-left: 0;
        border-top: 1px solid #e0e0e0;
    }
    .metastore-workbench-scroll { max-height: 520px; }
}
</style>
"""


class EmptyCapabilityState:
    """Neutral placeholder for intentionally unsupported metadata capabilities."""

    @staticmethod
    def render(title: str, description: str, icon: str) -> None:
        with ui.column().classes("w-full items-center justify-center q-pa-xl gap-2"):
            ui.icon(icon, color="grey-5", size="44px")
            ui.label(title).classes("text-subtitle1 text-grey-7")
            ui.label(description).classes("text-body2 text-grey-6 text-center").style(
                "max-width: 480px"
            )


class WorkbenchMetric:
    """Compact metric card used in the asset inspector."""

    def __init__(self, label: str, value: str, detail: str, icon: str, color: str) -> None:
        self._label = label
        self._value = value
        self._detail = detail
        self._icon = icon
        self._color = color

    def render(self) -> None:
        with ui.card().classes("q-pa-md col metastore-workbench-metric"):
            with ui.row().classes("items-start no-wrap gap-3"):
                with ui.element("span").classes("metastore-workbench-metric-icon"):
                    ui.icon(self._icon, color=self._color, size="24px")
                with ui.column().classes("gap-0 min-w-0"):
                    ui.label(self._label).classes("text-caption text-grey-6")
                    ui.label(self._value).classes("text-h6 text-weight-medium")
                    ui.label(self._detail).classes("text-caption text-grey-6 ellipsis")


class MetastoreWorkbench:
    """Coordinates the catalog tree, schema asset list, and live inspector."""

    def __init__(self, asset_service: MetastoreAssetService) -> None:
        self._asset_service = asset_service
        self._selected_path: AssetPath | None = None
        self._asset_list_container: ui.column | None = None
        self._detail_container: ui.column | None = None

    def render(self) -> None:
        ui.add_head_html(METASTORE_WORKBENCH_CSS)
        ui.query("body").style("overflow: hidden")

        with ui.column().classes("w-full gap-0 metastore-workbench-page"):
            self._render_page_header()
            with ui.element("div").classes("w-full metastore-workbench-shell"):
                self._render_catalog_pane()
                self._render_asset_pane()
                self._render_detail_pane()

        try:
            first_asset = self._asset_service.find_first_asset()
        except Exception as exc:
            self._render_page_error(str(exc))
            return
        if first_asset is not None:
            self._select_asset(first_asset)
        else:
            self._render_no_assets()

    @staticmethod
    def _render_page_header() -> None:
        with ui.row().classes("w-full items-center gap-3 q-px-md q-py-sm bg-white border-b"):
            ui.icon("storage", color="primary", size="28px")
            with ui.column().classes("gap-0"):
                ui.label("Metastore Workbench").classes("text-h5 text-weight-medium")
                ui.label("Browse live DuckLake catalogs, assets, schemas, and history.").classes(
                    "text-caption text-grey-6"
                )
            ui.space()
            ui.button(icon="refresh", on_click=lambda: ui.navigate.to("/explorer")).props(
                "flat round color=grey-7"
            ).tooltip("Refresh metadata")

    def _render_catalog_pane(self) -> None:
        with ui.column().classes("metastore-workbench-pane gap-0"):
            ui.label("Catalogs").classes("text-subtitle2 q-pa-sm bg-grey-2")
            with ui.scroll_area().classes("w-full col"):
                catalog_container = ui.column().classes("w-full")
            CatalogBrowser(
                container=catalog_container,
                on_table_select=self._select_qualified_asset,
            )

    def _render_asset_pane(self) -> None:
        with ui.column().classes("metastore-workbench-pane gap-0"):
            ui.label("Assets").classes("text-subtitle2 q-pa-sm bg-grey-2")
            self._asset_list_container = ui.column().classes(
                "w-full gap-0 metastore-workbench-scroll"
            )
            with self._asset_list_container:
                ui.label("Select a table or view from the catalog.").classes(
                    "text-caption text-grey-6 q-pa-md"
                )

    def _render_detail_pane(self) -> None:
        with ui.column().classes("metastore-workbench-pane gap-0"):
            ui.label("Inspector").classes("text-subtitle2 q-pa-sm bg-grey-2")
            self._detail_container = ui.column().classes("w-full gap-0 metastore-workbench-scroll")
            with self._detail_container:
                EmptyCapabilityState.render(
                    "Select an asset",
                    "Choose a table or view to inspect the metadata DuckLake currently exposes.",
                    "touch_app",
                )

    def _select_qualified_asset(self, qualified_name: str) -> None:
        try:
            self._select_asset(AssetPath.parse(qualified_name))
        except ValueError as exc:
            ui.notify(str(exc), type="negative")

    def _select_asset(self, path: AssetPath) -> None:
        self._selected_path = path
        self._render_schema_assets()
        self._render_asset_detail()

    def _render_schema_assets(self) -> None:
        if self._asset_list_container is None or self._selected_path is None:
            return
        self._asset_list_container.clear()
        assets = self._asset_service.list_schema_assets(self._selected_path)

        with self._asset_list_container:
            with ui.column().classes("w-full gap-0 q-pa-sm"):
                ui.label(self._selected_path.schema).classes("text-subtitle2")
                ui.label(f"{len(assets)} assets").classes("text-caption text-grey-6")
            search = (
                ui.input(placeholder="Filter this schema...")
                .props("dense outlined clearable prepend-icon=search")
                .classes("w-full q-px-sm q-pb-sm")
            )
            cards = ui.column().classes("w-full gap-1 q-px-sm q-pb-sm")

        def render_filtered_assets(query: str = "") -> None:
            normalized_query = query.strip().lower()
            visible_assets = tuple(
                asset
                for asset in assets
                if not normalized_query or normalized_query in asset.path.name.lower()
            )
            self._render_asset_cards(cards, visible_assets)

        search.on_value_change(lambda event: render_filtered_assets(event.value or ""))
        render_filtered_assets()

    def _render_asset_cards(
        self,
        container: ui.column,
        assets: Sequence[AssetListItem],
    ) -> None:
        container.clear()
        with container:
            if not assets:
                ui.label("No matching assets.").classes("text-caption text-grey-6 q-pa-sm")
                return
            for asset in assets:
                selected = self._selected_path == asset.path
                classes = "w-full q-pa-sm metastore-workbench-asset"
                if selected:
                    classes += " selected"
                with (
                    ui.card()
                    .classes(classes)
                    .on("click", lambda _, path=asset.path: self._select_asset(path))
                ):
                    with ui.row().classes("w-full items-center no-wrap gap-2"):
                        ui.icon(
                            "view_list" if asset.asset_type == "VIEW" else "table_chart",
                            color="primary" if selected else "grey-7",
                        )
                        with ui.column().classes("gap-0 col min-w-0"):
                            ui.label(asset.path.name).classes(
                                "text-body2 text-weight-medium ellipsis"
                            )
                            ui.label(self._display_asset_type(asset.asset_type)).classes(
                                "text-caption text-grey-6"
                            )

    def _render_asset_detail(self) -> None:
        if self._detail_container is None or self._selected_path is None:
            return
        self._detail_container.clear()
        try:
            asset = self._asset_service.load(self._selected_path)
        except Exception as exc:
            with self._detail_container:
                EmptyCapabilityState.render(
                    "Could not load metadata",
                    str(exc),
                    "error_outline",
                )
            return

        with self._detail_container:
            with ui.column().classes("w-full gap-4 q-pa-md"):
                self._render_asset_header(asset)
                self._render_metric_strip(asset)
                ui.separator()
                self._render_detail_tabs(asset)

    def _render_asset_header(self, asset: AssetMetadata) -> None:
        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("w-full items-start justify-between gap-3"):
                with ui.column().classes("gap-1 min-w-0"):
                    ui.label(asset.path.qualified_name).classes(
                        "text-h5 text-weight-medium text-grey-9 ellipsis"
                    ).tooltip(asset.path.qualified_name)
                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        ui.badge(
                            self._display_asset_type(asset.asset_type), color="blue-grey-6"
                        ).props("outline")
                        ui.badge("No tags configured", color="grey-6").props("outline")
                with ui.row().classes("items-center gap-1"):
                    ui.button(
                        "Copy path",
                        icon="content_copy",
                        on_click=lambda: ui.run_javascript(
                            f"navigator.clipboard.writeText({json.dumps(asset.path.qualified_name)})"
                        ),
                    ).props("flat dense color=grey-7")
                    ui.button(
                        "Query asset",
                        icon="open_in_new",
                        on_click=lambda: ui.navigate.to(
                            f"/query?table={quote(asset.path.qualified_name)}"
                        ),
                    ).props("outline dense color=primary")

            if asset.description:
                ui.label(asset.description).classes("text-body2 text-grey-8").style(
                    "max-width: 900px; white-space: pre-wrap"
                )
            else:
                ui.label("No table or view description has been added.").classes(
                    "text-body2 text-grey-6 text-italic"
                )

    def _render_metric_strip(self, asset: AssetMetadata) -> None:
        properties = asset.properties
        metrics = (
            WorkbenchMetric(
                "Estimated rows",
                self._format_count(properties.estimated_rows),
                "Not applicable to views" if asset.is_view else "DuckDB catalog estimate",
                "table_rows",
                "primary",
            ),
            WorkbenchMetric(
                "Data files",
                self._format_count(properties.file_count),
                self._format_bytes(properties.total_size_bytes),
                "database",
                "teal",
            ),
            WorkbenchMetric(
                "Quality",
                "—",
                "Not configured",
                QUALITY_ICON,
                "grey-6",
            ),
            WorkbenchMetric(
                "Usage",
                "—",
                "Not collected",
                "monitoring",
                "grey-6",
            ),
        )
        with ui.row().classes("w-full gap-3 flex-wrap"):
            for metric in metrics:
                metric.render()

    def _render_detail_tabs(self, asset: AssetMetadata) -> None:
        with ui.tabs().classes("w-full text-grey-7").props("dense align=left") as tabs:
            overview_tab = ui.tab("Overview", icon="info")
            columns_tab = ui.tab("Columns", icon="view_column")
            preview_tab = ui.tab("Preview", icon="preview")
            quality_tab = ui.tab("Quality", icon=QUALITY_ICON)
            history_tab = ui.tab("History", icon="history")
            lineage_tab = ui.tab("Lineage", icon="account_tree")

        with ui.tab_panels(tabs, value=overview_tab).classes("w-full bg-transparent"):
            with ui.tab_panel(overview_tab).classes("q-pa-md"):
                self._render_overview(asset)
            with ui.tab_panel(columns_tab).classes("q-pa-md"):
                self._render_columns(asset)
            with ui.tab_panel(preview_tab).classes("q-pa-md"):
                self._render_preview(asset)
            with ui.tab_panel(quality_tab).classes("q-pa-md"):
                EmptyCapabilityState.render(
                    "Quality is not configured",
                    "No quality rules or scores are collected for this asset.",
                    QUALITY_ICON,
                )
            with ui.tab_panel(history_tab).classes("q-pa-md"):
                self._render_history(asset)
            with ui.tab_panel(lineage_tab).classes("q-pa-md"):
                EmptyCapabilityState.render(
                    "Lineage is not available",
                    "DuckBricks is not collecting upstream or downstream relationships yet.",
                    "account_tree",
                )

    def _render_overview(self, asset: AssetMetadata) -> None:
        properties = asset.properties
        with ui.row().classes("w-full gap-6"):
            with ui.column().classes("gap-3 col"):
                self._property("Catalog", asset.path.catalog, "storage")
                self._property("Schema", asset.path.schema, "folder")
                self._property("Asset type", self._display_asset_type(asset.asset_type), "category")
                self._property("Columns", str(len(asset.columns)), "view_column")
            with ui.column().classes("gap-3 col"):
                self._property(
                    "DuckLake UUID", properties.asset_uuid or "Not available", "fingerprint"
                )
                self._property("Data path", properties.data_path, "folder_open")
                self._property("Snapshots affecting asset", str(len(asset.snapshots)), "history")

        if asset.view_definition:
            ui.label("View definition").classes("text-subtitle2 q-mt-lg q-mb-xs")
            ui.code(asset.view_definition, language="sql").classes("w-full")

    @staticmethod
    def _render_columns(asset: AssetMetadata) -> None:
        if not asset.columns:
            EmptyCapabilityState.render(
                "No columns available",
                "DuckDB did not return column metadata for this asset.",
                "view_column",
            )
            return
        search = (
            ui.input(placeholder="Search columns...")
            .props("dense outlined clearable prepend-icon=search")
            .classes("w-full q-mb-sm")
        )
        rows = [
            {
                "name": column.name,
                "type": column.data_type,
                "nullable": "Yes" if column.nullable else "No",
                "description": column.description or "—",
            }
            for column in asset.columns
        ]
        table = ui.table(
            columns=[
                {"name": "name", "label": "Column", "field": "name", "align": "left"},
                {"name": "type", "label": "Type", "field": "type", "align": "left"},
                {
                    "name": "nullable",
                    "label": "Nullable",
                    "field": "nullable",
                    "align": "left",
                },
                {
                    "name": "description",
                    "label": "Description",
                    "field": "description",
                    "align": "left",
                },
            ],
            rows=rows,
            row_key="name",
        ).classes("w-full")
        search.bind_value_to(table, "filter")

    def _render_preview(self, asset: AssetMetadata) -> None:
        ui.label("Preview reads up to 100 rows and does not mask sensitive values.").classes(
            "text-caption text-orange-8 q-mb-sm"
        )
        preview_container = ui.column().classes("w-full").style("min-height: 240px")

        def load_preview() -> None:
            result = self._asset_service.preview(asset.path)
            ResultsGrid().render(preview_container, result, auto_height=True)

        with preview_container:
            with ui.column().classes("w-full items-center q-pa-lg gap-2"):
                ui.icon("preview", color="grey-5", size="36px")
                ui.label("Preview is loaded only when requested.").classes("text-body2 text-grey-6")
                ui.button("Load preview", icon="play_arrow", on_click=load_preview).props(
                    "outline color=primary"
                )

    @staticmethod
    def _render_history(asset: AssetMetadata) -> None:
        if not asset.snapshots:
            EmptyCapabilityState.render(
                "No asset history found",
                "DuckLake did not return snapshots associated with this asset.",
                "history",
            )
            return
        ui.table(
            columns=[
                {"name": "id", "label": "Snapshot", "field": "id", "align": "left"},
                {"name": "time", "label": "Created", "field": "time", "align": "left"},
                {
                    "name": "operation",
                    "label": "Operation",
                    "field": "operation",
                    "align": "left",
                },
                {"name": "author", "label": "Author", "field": "author", "align": "left"},
                {
                    "name": "message",
                    "label": "Commit message",
                    "field": "message",
                    "align": "left",
                },
            ],
            rows=[
                {
                    "key": f"{snapshot.snapshot_id}:{snapshot.operation}",
                    "id": snapshot.snapshot_id,
                    "time": MetastoreWorkbench._format_timestamp(snapshot.snapshot_time),
                    "operation": snapshot.operation.replace("_", " ").title(),
                    "author": snapshot.author or "—",
                    "message": snapshot.commit_message or "—",
                }
                for snapshot in asset.snapshots
            ],
            row_key="key",
        ).classes("w-full")

    @staticmethod
    def _property(label: str, value: str, icon: str) -> None:
        with ui.row().classes("items-start no-wrap gap-2"):
            ui.icon(icon, color="grey-6", size="18px")
            with ui.column().classes("gap-0 min-w-0"):
                ui.label(label).classes("text-caption text-grey-6")
                ui.label(value).classes("text-body2 text-grey-9").style("word-break: break-word")

    def _render_page_error(self, error: str) -> None:
        if self._detail_container is None:
            return
        self._detail_container.clear()
        with self._detail_container:
            EmptyCapabilityState.render("Could not load the metastore", error, "error_outline")

    def _render_no_assets(self) -> None:
        if self._detail_container is None:
            return
        self._detail_container.clear()
        with self._detail_container:
            EmptyCapabilityState.render(
                "No tables or views",
                "Create an asset in DuckLake to inspect it here.",
                "table_chart",
            )

    @staticmethod
    def _display_asset_type(asset_type: str) -> str:
        return "View" if asset_type.upper() == "VIEW" else "Table"

    @staticmethod
    def _format_count(value: int | None) -> str:
        return "—" if value is None else f"{value:,}"

    @staticmethod
    def _format_bytes(value: int | None) -> str:
        if value is None:
            return "Not applicable"
        units = ("B", "KB", "MB", "GB", "TB")
        amount = float(value)
        unit = units[0]
        for candidate in units:
            unit = candidate
            if amount < 1024 or candidate == units[-1]:
                break
            amount /= 1024
        precision = 0 if unit == "B" else 1
        return f"{amount:.{precision}f} {unit}"

    @staticmethod
    def _format_timestamp(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat(sep=" ", timespec="seconds")
        return str(value)
