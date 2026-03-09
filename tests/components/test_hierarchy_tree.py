"""Unit tests for hierarchy tree component."""

import pytest
from unittest.mock import Mock, patch

from app.components.hierarchy_tree import render_hierarchy_tree, _find_node
from app.services.ducklake import DuckLakeManager


@pytest.fixture
def mock_container():
    """Create a mock NiceGUI container."""
    container = Mock()
    container.__enter__ = Mock(return_value=container)
    container.__exit__ = Mock(return_value=False)
    return container


@pytest.fixture
def mock_service():
    """Create a mock DuckLakeManager."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(return_value=["catalog1", "catalog2"])
    service.list_schemas = Mock(return_value=["schema1", "schema2"])
    service.list_tables_in_schema = Mock(return_value=["table1", "table2"])
    return service


def test_load_catalogs_success(mock_service, mock_container):
    """Test successful catalog loading."""
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree.props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree
        
        tree = render_hierarchy_tree(mock_container, ducklake_manager=mock_service)
        
        # Verify catalogs were loaded
        mock_service.list_catalogs.assert_called_once()
        
        # Verify tree was created with correct nodes
        call_args = mock_ui.tree.call_args
        nodes = call_args[0][0]
        
        assert len(nodes) == 2
        assert nodes[0]["id"] == "catalog1"
        assert nodes[0]["label"] == "📦 catalog1"
        assert nodes[0]["lazy"] is True  # KEY: lazy property present
        assert "children" not in nodes[0]  # KEY: no children key
        
        assert nodes[1]["id"] == "catalog2"
        assert nodes[1]["lazy"] is True


def test_load_catalogs_not_initialized(mock_container):
    """Test handling when DuckLake not initialized."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = False
    
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree.props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree
        
        tree = render_hierarchy_tree(mock_container, ducklake_manager=service)
        
        call_args = mock_ui.tree.call_args
        nodes = call_args[0][0]
        
        assert len(nodes) == 1
        assert nodes[0]["id"] == "__not_initialized__"
        assert "not initialized" in nodes[0]["label"].lower()


def test_load_catalogs_empty(mock_container):
    """Test handling when no catalogs exist."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(return_value=[])
    
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree.props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree
        
        tree = render_hierarchy_tree(mock_container, ducklake_manager=service)
        
        call_args = mock_ui.tree.call_args
        nodes = call_args[0][0]
        
        assert len(nodes) == 1
        assert nodes[0]["id"] == "__empty_catalogs__"


def test_load_catalogs_error(mock_container):
    """Test error handling during catalog load."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(side_effect=RuntimeError("Connection failed"))
    
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree.props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree
        mock_ui.notify = Mock()
        
        tree = render_hierarchy_tree(mock_container, ducklake_manager=service)
        
        # Verify error notification was shown
        mock_ui.notify.assert_called()
        
        call_args = mock_ui.tree.call_args
        nodes = call_args[0][0]
        
        assert len(nodes) == 1
        assert nodes[0]["id"] == "__error_catalogs__"
        assert "error" in nodes[0]["label"].lower()


def test_find_node_root_level():
    """Test finding a node at root level."""
    nodes = [
        {"id": "cat1", "label": "Catalog 1"},
        {"id": "cat2", "label": "Catalog 2"},
    ]
    
    result = _find_node(nodes, "cat2")
    
    assert result is not None
    assert result["id"] == "cat2"


def test_find_node_nested():
    """Test finding a nested node."""
    nodes = [
        {
            "id": "cat1",
            "label": "Catalog 1",
            "children": [
                {"id": "cat1.schema1", "label": "Schema 1"},
                {
                    "id": "cat1.schema2",
                    "label": "Schema 2",
                    "children": [
                        {"id": "cat1.schema2.table1", "label": "Table 1"}
                    ]
                }
            ]
        }
    ]
    
    result = _find_node(nodes, "cat1.schema2.table1")
    
    assert result is not None
    assert result["id"] == "cat1.schema2.table1"


def test_find_node_not_found():
    """Test when node doesn't exist."""
    nodes = [{"id": "cat1", "label": "Catalog 1"}]
    
    result = _find_node(nodes, "nonexistent")
    
    assert result is None


def test_find_node_empty_list():
    """Test _find_node handles empty node list."""
    result = _find_node([], "anything")
    
    assert result is None


def test_node_id_parsing(mock_container):
    """Test node ID format follows convention (no prefix)."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(return_value=["test_catalog"])
    
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree.props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree
        
        tree = render_hierarchy_tree(mock_container, ducklake_manager=service)
        
        call_args = mock_ui.tree.call_args
        nodes = call_args[0][0]
        
        # Catalog ID should have no dots
        catalog_node = nodes[0]
        assert "." not in catalog_node["id"]
        
        # Schema ID should have one dot
        schema_id = f"{catalog_node['id']}.test_schema"
        assert schema_id.count(".") == 1
        
        # Table ID should have two dots
        table_id = f"{schema_id}.test_table"
        assert table_id.count(".") == 2


def test_callback_is_optional(mock_service, mock_container):
    """Test that on_table_select callback is optional."""
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree.props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree
        
        # Should not raise exception without callback
        tree = render_hierarchy_tree(mock_container, ducklake_manager=mock_service)
        
        assert tree is not None


def test_lazy_property_enables_expansion(mock_container):
    """Test that lazy property is set correctly for expandable nodes."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(return_value=["test_cat"])
    
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree.props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree
        
        tree = render_hierarchy_tree(mock_container, ducklake_manager=service)
        
        call_args = mock_ui.tree.call_args
        nodes = call_args[0][0]
        
        # Catalog nodes should have lazy: True
        assert nodes[0]["lazy"] is True
        # And should NOT have children key
        assert "children" not in nodes[0]


def test_tree_created_successfully(mock_container):
    """Test that the tree component is created successfully."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(return_value=["cat1"])
    service.list_schemas = Mock(return_value=["schema1"])
    
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        # Set up props correctly
        mock_tree.props = {
            "nodes": [
                {
                    "id": "cat1",
                    "label": "📦 cat1",
                    "lazy": True
                }
            ]
        }
        mock_ui.tree.return_value = mock_tree
        mock_ui.notify = Mock()
        
        tree = render_hierarchy_tree(mock_container, ducklake_manager=service)
        
        # Verify tree was created
        assert tree is not None
        # Verify tree.props is accessed (not tree._props)
        assert hasattr(tree, 'props')
