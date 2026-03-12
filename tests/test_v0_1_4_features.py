"""Tests for v0.1.4 features (FR-4, FR-5, FR-6, FR-7)."""

import pytest
from app.services.ducklake import DuckLakeManager


@pytest.fixture
def initialized_manager(tmp_path):
    """Create and initialize a DuckLakeManager for testing."""
    from app.config import CATALOG_PATH, DATA_PATH
    import os
    
    # Use temp directory for testing
    test_catalog = tmp_path / "test_catalog.db"
    test_data = tmp_path / "data"
    test_data.mkdir(exist_ok=True)
    
    # Monkey-patch the config for testing
    original_catalog = CATALOG_PATH
    original_data = DATA_PATH
    
    import app.config
    app.config.CATALOG_PATH = str(test_catalog)
    app.config.DATA_PATH = str(test_data)
    
    manager = DuckLakeManager()
    manager.initialize()
    
    # Create a test table
    manager.execute_query(
        """
        CREATE TABLE test_sales (
            id INTEGER PRIMARY KEY,
            product_name VARCHAR,
            amount DECIMAL(10,2)
        )
        """
    )
    manager.execute_query(
        "INSERT INTO test_sales VALUES (1, 'Widget', 99.99), (2, 'Gadget', 49.99)"
    )
    
    yield manager
    
    # Cleanup
    app.config.CATALOG_PATH = original_catalog
    app.config.DATA_PATH = original_data


class TestSearchTables:
    """Tests for FR-5: SQL Autocomplete - search_tables method."""
    
    def test_search_tables_returns_list(self, initialized_manager):
        """search_tables should return a list of matching tables."""
        results = initialized_manager.search_tables("test")
        assert isinstance(results, list)
    
    def test_search_tables_finds_matching_table(self, initialized_manager):
        """search_tables should find tables matching the query."""
        results = initialized_manager.search_tables("sales")
        assert len(results) > 0
        assert any(r["table"] == "test_sales" for r in results)
    
    def test_search_tables_returns_correct_structure(self, initialized_manager):
        """search_tables should return dicts with expected keys."""
        results = initialized_manager.search_tables("test")
        if results:
            result = results[0]
            assert "full_name" in result
            assert "catalog" in result
            assert "schema" in result
            assert "table" in result
            assert "column_count" in result
    
    def test_search_tables_empty_query(self, initialized_manager):
        """search_tables should return empty list for empty query."""
        results = initialized_manager.search_tables("")
        assert results == []
    
    def test_search_tables_no_match(self, initialized_manager):
        """search_tables should return empty list when no tables match."""
        results = initialized_manager.search_tables("nonexistent_xyz_123")
        assert results == []
    
    def test_search_tables_case_insensitive(self, initialized_manager):
        """search_tables should be case insensitive."""
        results_lower = initialized_manager.search_tables("sales")
        results_upper = initialized_manager.search_tables("SALES")
        assert len(results_lower) == len(results_upper)


class TestCSVExport:
    """Tests for FR-6: CSV Export - export_results_to_csv method."""
    
    def test_export_results_to_csv_returns_bytes(self, initialized_manager):
        """export_results_to_csv should return bytes."""
        csv_data = initialized_manager.export_results_to_csv(
            "SELECT * FROM test_sales"
        )
        assert isinstance(csv_data, bytes)
    
    def test_export_results_to_csv_includes_header(self, initialized_manager):
        """export_results_to_csv should include column headers."""
        csv_data = initialized_manager.export_results_to_csv(
            "SELECT * FROM test_sales"
        )
        csv_text = csv_data.decode('utf-8')
        assert "id" in csv_text
        assert "product_name" in csv_text
        assert "amount" in csv_text
    
    def test_export_results_to_csv_includes_data(self, initialized_manager):
        """export_results_to_csv should include data rows."""
        csv_data = initialized_manager.export_results_to_csv(
            "SELECT * FROM test_sales"
        )
        csv_text = csv_data.decode('utf-8')
        assert "Widget" in csv_text
        assert "Gadget" in csv_text
    
    def test_export_results_to_csv_correct_row_count(self, initialized_manager):
        """export_results_to_csv should export correct number of rows."""
        csv_data = initialized_manager.export_results_to_csv(
            "SELECT * FROM test_sales"
        )
        csv_text = csv_data.decode('utf-8')
        lines = csv_text.strip().split('\n')
        # Header + 2 data rows
        assert len(lines) == 3
    
    def test_export_results_to_csv_handles_empty_result(self, initialized_manager):
        """export_results_to_csv should handle queries with no results."""
        csv_data = initialized_manager.export_results_to_csv(
            "SELECT * FROM test_sales WHERE id = 999"
        )
        csv_text = csv_data.decode('utf-8')
        lines = csv_text.strip().split('\n')
        # Just header row
        assert len(lines) == 1


class TestTableDetails:
    """Tests for FR-7: Metastore Details - get_table_details method."""
    
    def test_get_table_details_returns_dict(self, initialized_manager):
        """get_table_details should return a dictionary."""
        details = initialized_manager.get_table_details(
            "ducklake_metastore.main.test_sales"
        )
        assert isinstance(details, dict)
    
    def test_get_table_details_has_required_keys(self, initialized_manager):
        """get_table_details should return dict with expected keys."""
        details = initialized_manager.get_table_details(
            "ducklake_metastore.main.test_sales"
        )
        assert "partitions" in details
        assert "constraints" in details
        assert "file_count" in details
        assert "table_size_bytes" in details
        assert "row_count" in details
        assert "last_modified" in details
    
    def test_get_table_details_row_count(self, initialized_manager):
        """get_table_details should return correct row count."""
        details = initialized_manager.get_table_details(
            "ducklake_metastore.main.test_sales"
        )
        assert details["row_count"] == 2
    
    def test_get_table_details_invalid_format(self, initialized_manager):
        """get_table_details should raise error for invalid table name format."""
        with pytest.raises(ValueError):
            initialized_manager.get_table_details("invalid_table_name")


class TestTableHistory:
    """Tests for FR-7: Metastore History - get_table_history method."""
    
    def test_get_table_history_returns_list(self, initialized_manager):
        """get_table_history should return a list."""
        history = initialized_manager.get_table_history(
            "ducklake_metastore.main.test_sales"
        )
        assert isinstance(history, list)
    
    def test_get_table_history_currently_empty(self, initialized_manager):
        """get_table_history should currently return empty list (placeholder)."""
        # This is expected until DuckLake versioning is implemented
        history = initialized_manager.get_table_history(
            "ducklake_metastore.main.test_sales"
        )
        assert history == []


class TestUninitializedManager:
    """Tests that methods properly handle uninitialized manager."""
    
    def test_search_tables_requires_initialization(self):
        """search_tables should raise error when not initialized."""
        manager = DuckLakeManager()
        with pytest.raises(RuntimeError, match="not initialized"):
            manager.search_tables("test")
    
    def test_export_csv_requires_initialization(self):
        """export_results_to_csv should raise error when not initialized."""
        manager = DuckLakeManager()
        with pytest.raises(RuntimeError, match="not initialized"):
            manager.export_results_to_csv("SELECT 1")
    
    def test_get_table_details_requires_initialization(self):
        """get_table_details should raise error when not initialized."""
        manager = DuckLakeManager()
        with pytest.raises(RuntimeError, match="not initialized"):
            manager.get_table_details("catalog.schema.table")
    
    def test_get_table_history_requires_initialization(self):
        """get_table_history should raise error when not initialized."""
        manager = DuckLakeManager()
        with pytest.raises(RuntimeError, match="not initialized"):
            manager.get_table_history("catalog.schema.table")
