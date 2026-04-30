"""Unit tests for the SQL completion engine.

Covers SqlContextParser (is_after_table_context, is_after_column_context,
extract_table_aliases, extract_dot_prefix) and CompletionSchemaProvider.build()
across 50 scenarios including simple queries, CTEs, subqueries, multiple SELECTs,
JOINs, and error-handling edge cases.
"""

from unittest.mock import MagicMock

import pytest

from app.services.completion.schema_provider import CompletionSchemaProvider
from app.services.completion.sql_context_parser import SqlContextParser

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_metastore():
    """Return a mock MetastoreManager that reports itself as initialized."""
    m = MagicMock()
    m.is_initialized = True
    return m


# ─── is_after_table_context ───────────────────────────────────────────────────


class TestIsAfterTableContext:
    """SqlContextParser.is_after_table_context — 12 scenarios."""

    def test_simple_from_keyword_with_trailing_space(self):
        assert SqlContextParser.is_after_table_context("SELECT * FROM ") is True

    def test_from_with_partial_table_name(self):
        assert SqlContextParser.is_after_table_context("SELECT * FROM use") is True

    def test_from_with_schema_qualified_partial(self):
        assert SqlContextParser.is_after_table_context("SELECT * FROM main.") is True

    def test_join_keyword(self):
        assert SqlContextParser.is_after_table_context("SELECT id FROM t1 JOIN ") is True

    def test_left_join_continues_table_context(self):
        assert SqlContextParser.is_after_table_context("SELECT id FROM t1 LEFT JOIN sales.") is True

    def test_insert_into_triggers_table_context(self):
        assert SqlContextParser.is_after_table_context("INSERT INTO ") is True

    def test_update_triggers_table_context(self):
        assert SqlContextParser.is_after_table_context("UPDATE ") is True

    def test_cte_body_select_from(self):
        sql = "WITH cte AS (SELECT 1) SELECT * FROM "
        assert SqlContextParser.is_after_table_context(sql) is True

    def test_nested_subquery_inner_from(self):
        sql = "SELECT * FROM (SELECT id FROM "
        assert SqlContextParser.is_after_table_context(sql) is True

    def test_where_clause_is_not_table_context(self):
        assert SqlContextParser.is_after_table_context("SELECT * FROM t WHERE ") is False

    def test_select_clause_is_not_table_context(self):
        assert SqlContextParser.is_after_table_context("SELECT ") is False

    def test_after_semicolon_standalone_select(self):
        # A new SELECT after semicolon is not in table context until FROM appears.
        assert SqlContextParser.is_after_table_context("SELECT 1; SELECT ") is False


# ─── is_after_column_context ─────────────────────────────────────────────────


class TestIsAfterColumnContext:
    """SqlContextParser.is_after_column_context — 12 scenarios."""

    def test_bare_select_keyword(self):
        assert SqlContextParser.is_after_column_context("SELECT ") is True

    def test_select_after_one_column(self):
        assert SqlContextParser.is_after_column_context("SELECT id, ") is True

    def test_where_clause(self):
        assert SqlContextParser.is_after_column_context("SELECT id FROM t WHERE ") is True

    def test_and_continuation(self):
        assert SqlContextParser.is_after_column_context("SELECT * FROM t WHERE x = 1 AND ") is True

    def test_or_continuation(self):
        assert SqlContextParser.is_after_column_context("SELECT * FROM t WHERE x = 1 OR ") is True

    def test_group_by_clause(self):
        assert SqlContextParser.is_after_column_context("SELECT * FROM t GROUP BY ") is True

    def test_order_by_clause(self):
        assert SqlContextParser.is_after_column_context("SELECT * FROM t ORDER BY ") is True

    def test_having_clause(self):
        assert SqlContextParser.is_after_column_context("SELECT * FROM t HAVING ") is True

    def test_on_condition_in_join(self):
        assert SqlContextParser.is_after_column_context("SELECT * FROM t1 JOIN t2 ON ") is True

    def test_set_clause_in_update(self):
        assert SqlContextParser.is_after_column_context("UPDATE t SET ") is True

    def test_cte_inner_select(self):
        assert SqlContextParser.is_after_column_context("WITH cte AS (SELECT ") is True

    def test_after_semicolon_new_select(self):
        # Semicolon resets context; the new SELECT is in column context.
        assert SqlContextParser.is_after_column_context("SELECT 1; SELECT ") is True


# ─── extract_table_aliases ────────────────────────────────────────────────────


class TestExtractTableAliases:
    """SqlContextParser.extract_table_aliases — 16 scenarios."""

    def test_simple_table_no_alias(self):
        result = SqlContextParser.extract_table_aliases("SELECT * FROM users")
        assert result.get("users") == "users"

    def test_implicit_alias(self):
        result = SqlContextParser.extract_table_aliases("SELECT * FROM users u")
        assert result.get("u") == "users"
        assert result.get("users") == "users"

    def test_explicit_as_alias(self):
        result = SqlContextParser.extract_table_aliases("SELECT * FROM users AS u")
        assert result.get("u") == "users"
        assert result.get("users") == "users"

    def test_schema_qualified_no_alias(self):
        # "main.users" is registered under the bare name only; the full dotted
        # path is not stored as a key (aliases map to paths, not the other way).
        result = SqlContextParser.extract_table_aliases("SELECT * FROM main.users")
        assert result.get("users") == "main.users"

    def test_schema_qualified_with_alias(self):
        result = SqlContextParser.extract_table_aliases("SELECT * FROM main.orders AS o")
        assert result.get("o") == "main.orders"
        assert result.get("orders") == "main.orders"

    def test_inner_join_two_tables(self):
        sql = "SELECT * FROM t1 JOIN t2 ON t1.id = t2.id"
        result = SqlContextParser.extract_table_aliases(sql)
        assert result.get("t1") == "t1"
        assert result.get("t2") == "t2"

    def test_multiple_chained_joins(self):
        sql = (
            "SELECT * FROM orders o JOIN products p ON o.pid = p.id"
            " JOIN customers c ON o.cid = c.id"
        )
        result = SqlContextParser.extract_table_aliases(sql)
        assert result.get("o") == "orders"
        assert result.get("p") == "products"
        assert result.get("c") == "customers"

    def test_three_part_fully_qualified_name(self):
        sql = "SELECT * FROM catalog.schema.tbl"
        result = SqlContextParser.extract_table_aliases(sql)
        assert result.get("tbl") == "catalog.schema.tbl"

    def test_cross_join(self):
        sql = "SELECT * FROM a CROSS JOIN b"
        result = SqlContextParser.extract_table_aliases(sql)
        assert result.get("a") == "a"
        assert result.get("b") == "b"

    def test_cte_referenced_in_from(self):
        sql = "WITH summary AS (SELECT id FROM raw) SELECT * FROM summary"
        result = SqlContextParser.extract_table_aliases(sql)
        # Both FROM raw (inside CTE) and FROM summary (outer) should be captured.
        assert result.get("raw") == "raw"
        assert result.get("summary") == "summary"

    def test_subquery_inner_table_is_captured(self):
        sql = "SELECT * FROM (SELECT id FROM orders) subq"
        result = SqlContextParser.extract_table_aliases(sql)
        # The outer FROM (SELECT…) won't match because '(' is not \w.
        # The inner FROM orders is captured.
        assert result.get("orders") == "orders"

    def test_self_join_same_table_two_aliases(self):
        sql = "SELECT * FROM employees e1 JOIN employees e2 ON e1.mgr_id = e2.id"
        result = SqlContextParser.extract_table_aliases(sql)
        # e2 registration overwrites e1 but both point to "employees"
        assert result.get("e1") == "employees"
        assert result.get("employees") == "employees"

    def test_multi_statement_both_tables_captured(self):
        sql = "SELECT * FROM t1; SELECT * FROM t2"
        result = SqlContextParser.extract_table_aliases(sql)
        assert result.get("t1") == "t1"
        assert result.get("t2") == "t2"

    def test_backtick_quoted_identifier(self):
        sql = "SELECT * FROM `my_table` AS mt"
        result = SqlContextParser.extract_table_aliases(sql)
        assert result.get("mt") == "my_table"

    def test_empty_sql_returns_empty_dict(self):
        result = SqlContextParser.extract_table_aliases("")
        assert result == {}

    def test_multiple_ctes_all_references_captured(self):
        sql = (
            "WITH a AS (SELECT * FROM raw_a), "
            "b AS (SELECT * FROM raw_b) "
            "SELECT * FROM a JOIN b ON a.id = b.id"
        )
        result = SqlContextParser.extract_table_aliases(sql)
        assert result.get("raw_a") == "raw_a"
        assert result.get("raw_b") == "raw_b"
        assert result.get("a") == "a"
        assert result.get("b") == "b"


# ─── extract_dot_prefix ───────────────────────────────────────────────────────


class TestExtractDotPrefix:
    """SqlContextParser.extract_dot_prefix — 5 scenarios."""

    def test_alias_dot_column(self):
        assert SqlContextParser.extract_dot_prefix("t.col") == "t"

    def test_schema_dot_table(self):
        assert SqlContextParser.extract_dot_prefix("schema.table") == "schema"

    def test_three_part_name_returns_two_part_prefix(self):
        assert SqlContextParser.extract_dot_prefix("catalog.schema.tbl") == "catalog.schema"

    def test_bare_word_returns_none(self):
        assert SqlContextParser.extract_dot_prefix("users") is None

    def test_empty_string_returns_none(self):
        assert SqlContextParser.extract_dot_prefix("") is None


# ─── CompletionSchemaProvider.build() ────────────────────────────────────────


class TestCompletionSchemaProviderBuild:
    """CompletionSchemaProvider.build() — 10 scenarios."""

    def test_returns_empty_dict_when_not_initialized(self):
        metastore = MagicMock()
        metastore.is_initialized = False
        provider = CompletionSchemaProvider(metastore)
        assert provider.build() == {}

    def test_each_table_registered_under_three_paths(self, mock_metastore):
        mock_metastore.list_catalogs.return_value = ["cat"]
        mock_metastore.list_schemas.return_value = ["sch"]
        mock_metastore.list_tables_in_schema_with_types.return_value = [{"name": "tbl"}]
        mock_metastore.list_columns.return_value = [{"name": "id", "type": "INTEGER"}]

        result = CompletionSchemaProvider(mock_metastore).build()

        assert "tbl" in result
        assert "sch.tbl" in result
        assert "cat.sch.tbl" in result

    def test_column_metadata_preserved_on_all_paths(self, mock_metastore):
        columns = [{"name": "user_id", "type": "BIGINT"}, {"name": "email", "type": "VARCHAR"}]
        mock_metastore.list_catalogs.return_value = ["main"]
        mock_metastore.list_schemas.return_value = ["public"]
        mock_metastore.list_tables_in_schema_with_types.return_value = [{"name": "users"}]
        mock_metastore.list_columns.return_value = columns

        result = CompletionSchemaProvider(mock_metastore).build()

        assert result["users"] == columns
        assert result["public.users"] == columns
        assert result["main.public.users"] == columns

    def test_handles_list_catalogs_exception(self, mock_metastore):
        mock_metastore.list_catalogs.side_effect = RuntimeError("DB unavailable")
        result = CompletionSchemaProvider(mock_metastore).build()
        assert result == {}

    def test_handles_list_schemas_exception_for_one_catalog(self, mock_metastore):
        mock_metastore.list_catalogs.return_value = ["cat_ok", "cat_bad"]
        mock_metastore.list_schemas.side_effect = lambda cat: (
            ["sch"] if cat == "cat_ok" else (_ for _ in ()).throw(RuntimeError("error"))
        )
        mock_metastore.list_tables_in_schema_with_types.return_value = [{"name": "t"}]
        mock_metastore.list_columns.return_value = []

        result = CompletionSchemaProvider(mock_metastore).build()
        # Only cat_ok's table should be present
        assert "t" in result

    def test_handles_list_tables_exception_for_one_schema(self, mock_metastore):
        mock_metastore.list_catalogs.return_value = ["cat"]
        mock_metastore.list_schemas.return_value = ["good_sch", "bad_sch"]
        mock_metastore.list_tables_in_schema_with_types.side_effect = lambda cat, sch: (
            [{"name": "t"}] if sch == "good_sch" else (_ for _ in ()).throw(RuntimeError())
        )
        mock_metastore.list_columns.return_value = []

        result = CompletionSchemaProvider(mock_metastore).build()
        assert "t" in result

    def test_multiple_tables_in_same_schema_all_registered(self, mock_metastore):
        mock_metastore.list_catalogs.return_value = ["main"]
        mock_metastore.list_schemas.return_value = ["public"]
        mock_metastore.list_tables_in_schema_with_types.return_value = [
            {"name": "orders"},
            {"name": "products"},
            {"name": "customers"},
        ]
        mock_metastore.list_columns.return_value = []

        result = CompletionSchemaProvider(mock_metastore).build()

        for table in ("orders", "products", "customers"):
            assert table in result
            assert f"public.{table}" in result
            assert f"main.public.{table}" in result

    def test_multiple_schemas_across_one_catalog(self, mock_metastore):
        mock_metastore.list_catalogs.return_value = ["main"]
        mock_metastore.list_schemas.return_value = ["raw", "staging"]
        mock_metastore.list_tables_in_schema_with_types.side_effect = lambda cat, sch: (
            [{"name": "events"}] if sch == "raw" else [{"name": "events_clean"}]
        )
        mock_metastore.list_columns.return_value = []

        result = CompletionSchemaProvider(mock_metastore).build()

        assert "raw.events" in result
        assert "staging.events_clean" in result

    def test_multiple_catalogs_produce_distinct_paths(self, mock_metastore):
        mock_metastore.list_catalogs.return_value = ["cat_a", "cat_b"]
        mock_metastore.list_schemas.return_value = ["sch"]
        mock_metastore.list_tables_in_schema_with_types.return_value = [{"name": "t"}]
        mock_metastore.list_columns.return_value = [{"name": "col", "type": "TEXT"}]

        result = CompletionSchemaProvider(mock_metastore).build()

        assert "cat_a.sch.t" in result
        assert "cat_b.sch.t" in result

    def test_empty_metastore_returns_empty_dict(self, mock_metastore):
        mock_metastore.list_catalogs.return_value = []
        result = CompletionSchemaProvider(mock_metastore).build()
        assert result == {}
