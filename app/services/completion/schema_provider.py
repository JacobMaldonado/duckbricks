"""SQL completion schema provider — builds CodeMirror-compatible schema from the metastore."""

from app.services.metastore.ducklake_manager import MetastoreManager


class CompletionSchemaProvider:
    """Extracts the full catalog structure and formats it for CodeMirror SQL completion.

    Output format: {qualified_table_path: [{"name": col, "type": dtype}]}

    Each table is registered under three resolvable paths:
    - table_name
    - schema.table_name
    - catalog.schema.table_name
    """

    def __init__(self, metastore: MetastoreManager) -> None:
        self._metastore = metastore

    def build(self) -> dict[str, list[dict]]:
        """Return schema dict keyed by all resolvable table paths."""
        if not self._metastore.is_initialized:
            return {}

        schema: dict[str, list[dict]] = {}
        try:
            catalogs = self._metastore.list_catalogs()
        except Exception:
            return {}

        for catalog in catalogs:
            try:
                schemas = self._metastore.list_schemas(catalog)
            except Exception:
                continue

            for schema_name in schemas:
                try:
                    tables = self._metastore.list_tables_in_schema_with_types(catalog, schema_name)
                except Exception:
                    continue

                for table_info in tables:
                    table_name = table_info["name"]
                    columns = self._metastore.list_columns(catalog, schema_name, table_name)
                    for path in (
                        table_name,
                        f"{schema_name}.{table_name}",
                        f"{catalog}.{schema_name}.{table_name}",
                    ):
                        schema[path] = columns

        return schema
