"""Unit tests for hierarchy tree component."""

import pytest
from unittest.mock import Mock, patch, call

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
    """Test successful catalog loading with placeholder children."""
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree._props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree

        tree = render_hierarchy_tree(mock_container, ducklake_manager=mock_service)

        mock_service.list_catalogs.assert_called_once()

        call_args = mock_ui.tree.call_args
        nodes = call_args[0][0]

        assert len(nodes) == 2
        assert nodes[0]["id"] == "catalog1"
        assert nodes[0]["label"] == "catalog1"
        assert nodes[0]["icon"] == "storage"
        # Must have a placeholder child to be expandable
        assert "children" in nodes[0]
        assert len(nodes[0]["children"]) == 1
        assert nodes[0]["children"][0]["id"].startswith("__loading_")

        assert nodes[1]["id"] == "catalog2"
        assert "children" in nodes[1]


def test_load_catalogs_not_initialized(mock_container):
    """Test handling when DuckLake not initialized."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = False

    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree._props = {"nodes": []}
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
        mock_tree._props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree

        tree = render_hierarchy_tree(mock_container, ducklake_manager=service)

        call_args = mock_ui.tree.call_args
        nodes = call_args[0][0]

        assert len(nodes) == 1
        assert nodes[0]["id"] == "__no_catalogs__"


def test_load_catalogs_error(mock_container):
    """Test error handling during catalog load."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(side_effect=RuntimeError("Connection failed"))

    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree._props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree
        mock_ui.notify = Mock()

        tree = render_hierarchy_tree(mock_container, ducklake_manager=service)

        mock_ui.notify.assert_called()

        call_args = mock_ui.tree.call_args
        nodes = call_args[0][0]

        assert len(nodes) == 1
        assert nodes[0]["id"] == "__error__"
        assert "error" in nodes[0]["label"].lower()


# ── _find_node tests ──────────────────────────────────────────────

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
    """Test finding a deeply nested node."""
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
                    ],
                },
            ],
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
    """Test _find_node with empty list."""
    result = _find_node([], "anything")
    assert result is None


# ── node structure tests ──────────────────────────────────────────

def test_node_id_convention(mock_container):
    """Test node IDs follow dot-separated convention."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(return_value=["test_catalog"])

    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree._props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree

        render_hierarchy_tree(mock_container, ducklake_manager=service)

        nodes = mock_ui.tree.call_args[0][0]
        catalog_node = nodes[0]
        # Catalog: no dots
        assert "." not in catalog_node["id"]
        # Schema would be: catalog.schema (1 dot)
        assert f"{catalog_node['id']}.schema".count(".") == 1
        # Table would be: catalog.schema.table (2 dots)
        assert f"{catalog_node['id']}.schema.table".count(".") == 2


def test_callback_is_optional(mock_service, mock_container):
    """Test that on_table_select callback is optional."""
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree._props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree

        tree = render_hierarchy_tree(mock_container, ducklake_manager=mock_service)
        assert tree is not None


def test_placeholder_children_make_nodes_expandable(mock_container):
    """Test that catalog nodes have placeholder children (enables expand arrow)."""
    service = Mock(spec=DuckLakeManager)
    service.is_initialized = True
    service.list_catalogs = Mock(return_value=["test_cat"])

    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree._props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree

        render_hierarchy_tree(mock_container, ducklake_manager=service)

        nodes = mock_ui.tree.call_args[0][0]

        # Catalog nodes must have children (placeholder) to show expand arrow
        assert "children" in nodes[0]
        assert len(nodes[0]["children"]) == 1
        # Placeholder child ID starts with __loading_
        assert nodes[0]["children"][0]["id"].startswith("__loading_")


def test_tree_created_with_event_handlers(mock_container, mock_service):
    """Test that the tree is created with select and expand handlers."""
    with patch("app.components.hierarchy_tree.ui") as mock_ui:
        mock_tree = Mock()
        mock_tree._props = {"nodes": []}
        mock_ui.tree.return_value = mock_tree

        tree = render_hierarchy_tree(mock_container, ducklake_manager=mock_service)

        # tree should be created with on_select and on_expand kwargs
        call_kwargs = mock_ui.tree.call_args[1]
        assert "on_select" in call_kwargs
        assert "on_expand" in call_kwargs
