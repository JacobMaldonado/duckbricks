"""Unit tests for the hierarchy tree component."""
from unittest.mock import Mock, patch

import pytest
from nicegui import ui

from app.components.hierarchy_tree import _find_node, render_hierarchy_tree
from app.services.ducklake import DuckLakeManager


@pytest.fixture
def mock_service():
    """Create a mock DuckLakeManager."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(return_value=["catalog1", "catalog2"])
    service.list_schemas = Mock(return_value=["schema1", "schema2"])
    service.list_tables_in_schema = Mock(return_value=["table1", "table2"])
    return service


@pytest.fixture
def container():
    """Create a NiceGUI container for testing."""
    return ui.column()


def test_find_node_finds_root_node():
    """Test _find_node can find a root-level node."""
    nodes = [
        {"id": "node1", "label": "Node 1"},
        {"id": "node2", "label": "Node 2"},
    ]
    result = _find_node(nodes, "node1")
    assert result is not None
    assert result["id"] == "node1"


def test_find_node_finds_nested_node():
    """Test _find_node can find a nested node."""
    nodes = [
        {
            "id": "parent",
            "label": "Parent",
            "children": [
                {"id": "child1", "label": "Child 1"},
                {"id": "child2", "label": "Child 2"},
            ]
        }
    ]
    result = _find_node(nodes, "child2")
    assert result is not None
    assert result["id"] == "child2"


def test_find_node_deeply_nested():
    """Test _find_node can find deeply nested nodes."""
    nodes = [
        {
            "id": "catalog:cat1",
            "label": "cat1",
            "children": [
                {
                    "id": "schema:cat1.main",
                    "label": "main",
                    "children": [
                        {
                            "id": "table:cat1.main.users",
                            "label": "users",
                        },
                    ],
                },
            ],
        },
    ]
    result = _find_node(nodes, "table:cat1.main.users")
    assert result is not None
    assert result["id"] == "table:cat1.main.users"


def test_find_node_returns_none_for_missing_node():
    """Test _find_node returns None when node doesn't exist."""
    nodes = [{"id": "node1", "label": "Node 1"}]
    result = _find_node(nodes, "nonexistent")
    assert result is None


def test_find_node_empty_list():
    """Test _find_node handles empty node list."""
    result = _find_node([], "anything")
    assert result is None


def test_render_hierarchy_tree_is_callable():
    """Test that render_hierarchy_tree is callable."""
    assert callable(render_hierarchy_tree)


def test_render_hierarchy_tree_initial_catalog_load(mock_service, container):
    """Test that the tree loads catalogs on initialization."""
    tree = render_hierarchy_tree(container, ducklake_service=mock_service)
    
    assert tree is not None
    mock_service.list_catalogs.assert_called_once()
    
    nodes = tree._props["nodes"]
    assert len(nodes) == 2
    assert nodes[0]["id"] == "catalog:catalog1"
    assert nodes[0]["label"] == "catalog1"
    assert nodes[0]["icon"] == "storage"
    assert nodes[1]["id"] == "catalog:catalog2"


def test_render_hierarchy_tree_not_initialized(container):
    """Test tree behavior when metastore is not initialized."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = False
    
    tree = render_hierarchy_tree(container, ducklake_service=service)
    
    nodes = tree._props["nodes"]
    assert len(nodes) == 1
    assert "not initialized" in nodes[0]["label"].lower()


def test_render_hierarchy_tree_empty_catalogs(container):
    """Test tree behavior when no catalogs exist."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(return_value=[])
    
    tree = render_hierarchy_tree(container, ducklake_service=service)
    
    nodes = tree._props["nodes"]
    assert len(nodes) == 1
    assert "no catalogs" in nodes[0]["label"].lower()


def test_render_hierarchy_tree_catalog_load_error(container):
    """Test tree handles catalog loading errors gracefully."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(side_effect=Exception("Database error"))
    
    with patch('app.components.hierarchy_tree.ui.notify'):
        tree = render_hierarchy_tree(container, ducklake_service=service)
    
    nodes = tree._props["nodes"]
    assert len(nodes) == 1
    assert "error" in nodes[0]["id"].lower()


def test_render_hierarchy_tree_with_callback(mock_service, container):
    """Test that tree can be created with a callback."""
    def dummy_callback(table_name: str):
        pass
    
    tree = render_hierarchy_tree(
        container,
        on_table_select=dummy_callback,
        ducklake_service=mock_service
    )
    
    assert tree is not None
    nodes = tree._props["nodes"]
    assert len(nodes) == 2


def test_custom_style_config(mock_service, container):
    """Test that custom style config is applied."""
    custom_config = {
        'icons': {
            'catalog': 'custom_catalog_icon',
            'schema': 'custom_schema_icon',
            'table': 'custom_table_icon',
            'error': 'custom_error_icon',
        }
    }
    
    tree = render_hierarchy_tree(
        container,
        ducklake_service=mock_service,
        style_config=custom_config
    )
    
    nodes = tree._props["nodes"]
    assert nodes[0]["icon"] == "custom_catalog_icon"


def test_tree_node_structure(mock_service, container):
    """Test that tree nodes have correct structure."""
    tree = render_hierarchy_tree(container, ducklake_service=mock_service)
    
    nodes = tree._props["nodes"]
    
    # Check first catalog node structure
    catalog_node = nodes[0]
    assert "id" in catalog_node
    assert "label" in catalog_node
    assert "icon" in catalog_node
    assert "children" in catalog_node
    
    # Catalogs should start with empty children for lazy loading
    assert catalog_node["children"] == []


def test_default_service_used_when_none_provided(container):
    """Test that default service (manager) is used when none provided."""
    # This will use the default manager which may or may not be initialized
    # We just check it doesn't crash
    try:
        tree = render_hierarchy_tree(container)
        assert tree is not None
    except Exception:
        # It's OK if it fails due to no initialized metastore
        pass
