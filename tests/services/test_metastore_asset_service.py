"""Tests for the Workbench metastore read service."""

from unittest.mock import Mock

import pytest

from app.services.metastore.asset_service import AssetPath, MetastoreAssetService
from app.services.metastore.ducklake_manager import MetastoreManager


def test_asset_path_parses_and_quotes_qualified_names() -> None:
    path = AssetPath.parse('catalog.sales.order"items')

    assert path.qualified_name == 'catalog.sales.order"items'
    assert path.sql_identifier == '"catalog"."sales"."order""items"'


@pytest.mark.parametrize("path", ("table", "schema.table", "a.b.c.d", "a..c"))
def test_asset_path_rejects_non_qualified_names(path: str) -> None:
    with pytest.raises(ValueError, match="catalog.schema.name"):
        AssetPath.parse(path)


def test_asset_service_builds_metadata_from_existing_sources() -> None:
    manager = Mock(spec=MetastoreManager)
    manager.get_asset_type.return_value = "BASE TABLE"
    manager.list_columns.return_value = [
        {
            "name": "id",
            "type": "BIGINT",
            "nullable": False,
            "description": "Primary identifier",
        }
    ]
    manager.get_table_history.return_value = [
        {
            "snapshot_id": 7,
            "snapshot_time": "2026-08-24",
            "operation": "tables_inserted_into",
            "author": None,
            "commit_message": None,
        }
    ]
    manager.get_table_properties.return_value = {
        "estimated_rows": 42,
        "file_count": 1,
        "total_size_bytes": 2048,
        "data_path": "/data/parquet",
        "asset_uuid": "asset-uuid",
    }
    manager.get_table_comment.return_value = "Orders"
    manager.get_view_definition.return_value = None
    service = MetastoreAssetService(manager)

    asset = service.load(AssetPath("catalog", "sales", "orders"))

    assert asset.description == "Orders"
    assert asset.columns[0].description == "Primary identifier"
    assert asset.properties.estimated_rows == 42
    assert asset.snapshots[0].snapshot_id == 7
    assert asset.is_view is False


def test_asset_service_lists_assets_from_selected_schema() -> None:
    manager = Mock(spec=MetastoreManager)
    manager.list_tables_in_schema_with_types.return_value = [
        {"name": "orders", "table_type": "BASE TABLE"},
        {"name": "daily_orders", "table_type": "VIEW"},
    ]
    service = MetastoreAssetService(manager)

    assets = service.list_schema_assets(AssetPath("catalog", "sales", "orders"))

    assert [asset.path.qualified_name for asset in assets] == [
        "catalog.sales.orders",
        "catalog.sales.daily_orders",
    ]
    assert assets[1].asset_type == "VIEW"


def test_preview_quotes_identifiers_and_caps_limit() -> None:
    manager = Mock(spec=MetastoreManager)
    manager.execute_query_typed.return_value = {"success": True, "rows": []}
    service = MetastoreAssetService(manager)

    service.preview(AssetPath("catalog", "sales", 'order"items'), limit=500)

    manager.execute_query_typed.assert_called_once_with(
        'SELECT * FROM "catalog"."sales"."order""items" LIMIT 100'
    )


def test_asset_path_can_build_query_editor_statement() -> None:
    path = AssetPath.parse("catalog.sales.orders")

    assert f"SELECT * FROM {path.sql_identifier} LIMIT 100;" == (
        'SELECT * FROM "catalog"."sales"."orders" LIMIT 100;'
    )
