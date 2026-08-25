"""Read-side models and service for the Metastore Workbench."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.metastore.ducklake_manager import MetastoreManager


@dataclass(frozen=True)
class AssetPath:
    """A catalog-qualified table or view identifier."""

    catalog: str
    schema: str
    name: str

    @classmethod
    def parse(cls, qualified_name: str) -> AssetPath:
        parts = qualified_name.split(".")
        if len(parts) != 3 or any(not part for part in parts):
            raise ValueError("Asset paths must use the catalog.schema.name format")
        return cls(catalog=parts[0], schema=parts[1], name=parts[2])

    @property
    def qualified_name(self) -> str:
        return f"{self.catalog}.{self.schema}.{self.name}"

    @property
    def sql_identifier(self) -> str:
        return ".".join(self._quote_identifier(part) for part in self.parts)

    @property
    def parts(self) -> tuple[str, str, str]:
        return self.catalog, self.schema, self.name

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


@dataclass(frozen=True)
class AssetListItem:
    """Compact asset identity rendered in the Workbench list."""

    path: AssetPath
    asset_type: str


@dataclass(frozen=True)
class AssetColumn:
    """Column metadata exposed by DuckDB's information schema."""

    name: str
    data_type: str
    nullable: bool
    description: str | None


@dataclass(frozen=True)
class AssetSnapshot:
    """A DuckLake snapshot that affected an asset."""

    snapshot_id: int
    snapshot_time: Any
    operation: str
    author: str | None
    commit_message: str | None


@dataclass(frozen=True)
class AssetProperties:
    """Physical and catalog properties available for an asset."""

    estimated_rows: int | None
    file_count: int | None
    total_size_bytes: int | None
    data_path: str
    asset_uuid: str | None


@dataclass(frozen=True)
class AssetMetadata:
    """Live metadata required by the selected Workbench design."""

    path: AssetPath
    asset_type: str
    description: str | None
    view_definition: str | None
    columns: tuple[AssetColumn, ...]
    snapshots: tuple[AssetSnapshot, ...]
    properties: AssetProperties

    @property
    def is_view(self) -> bool:
        return self.asset_type.upper() == "VIEW"


class MetastoreAssetService:
    """Builds Workbench assets from metadata already exposed by DuckLake."""

    def __init__(self, metastore: MetastoreManager) -> None:
        self._metastore = metastore

    def find_first_asset(self) -> AssetPath | None:
        for catalog in self._metastore.list_catalogs():
            for schema in self._metastore.list_schemas(catalog):
                assets = self._metastore.list_tables_in_schema_with_types(catalog, schema)
                if assets:
                    return AssetPath(catalog, schema, assets[0]["name"])
        return None

    def list_schema_assets(self, selected: AssetPath) -> tuple[AssetListItem, ...]:
        assets = self._metastore.list_tables_in_schema_with_types(
            selected.catalog,
            selected.schema,
        )
        return tuple(
            AssetListItem(
                path=AssetPath(selected.catalog, selected.schema, asset["name"]),
                asset_type=asset["table_type"],
            )
            for asset in assets
        )

    def load(self, path: AssetPath) -> AssetMetadata:
        asset_type = self._metastore.get_asset_type(*path.parts)
        if asset_type is None:
            raise KeyError(f"Unknown metastore asset: {path.qualified_name}")

        columns = tuple(
            AssetColumn(
                name=column["name"],
                data_type=column["type"],
                nullable=column["nullable"],
                description=column["description"],
            )
            for column in self._metastore.list_columns(*path.parts)
        )
        snapshots = tuple(
            AssetSnapshot(
                snapshot_id=snapshot["snapshot_id"],
                snapshot_time=snapshot["snapshot_time"],
                operation=snapshot["operation"],
                author=snapshot["author"],
                commit_message=snapshot["commit_message"],
            )
            for snapshot in self._metastore.get_table_history(*path.parts)
        )
        properties = self._metastore.get_table_properties(*path.parts)

        return AssetMetadata(
            path=path,
            asset_type=asset_type,
            description=self._metastore.get_table_comment(*path.parts),
            view_definition=self._metastore.get_view_definition(*path.parts),
            columns=columns,
            snapshots=snapshots,
            properties=AssetProperties(
                estimated_rows=properties["estimated_rows"],
                file_count=properties["file_count"],
                total_size_bytes=properties["total_size_bytes"],
                data_path=properties["data_path"],
                asset_uuid=properties["asset_uuid"],
            ),
        )

    def preview(self, path: AssetPath, limit: int = 100) -> dict:
        safe_limit = max(1, min(limit, 100))
        return self._metastore.execute_query_typed(
            f"SELECT * FROM {path.sql_identifier} LIMIT {safe_limit}"
        )
