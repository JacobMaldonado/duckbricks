"""Tests for the Query Workspace page."""


def test_query_workspace_is_importable():
    """query_workspace function should be importable."""
    from app.pages.query import query_workspace

    assert callable(query_workspace)


def test_build_catalog_tree_is_importable():
    """_build_catalog_tree helper should be importable."""
    from app.pages.query import _build_catalog_tree

    assert callable(_build_catalog_tree)


def test_find_node_finds_top_level():
    """_find_node should find top-level nodes."""
    from app.pages.query import _find_node

    nodes = [
        {"id": "cat1", "label": "Cat 1", "children": []},
        {"id": "cat2", "label": "Cat 2", "children": []},
    ]
    assert _find_node(nodes, "cat1")["label"] == "Cat 1"
    assert _find_node(nodes, "cat2")["label"] == "Cat 2"


def test_find_node_finds_nested():
    """_find_node should find nested nodes."""
    from app.pages.query import _find_node

    nodes = [
        {
            "id": "cat1",
            "label": "Cat 1",
            "children": [
                {
                    "id": "cat1.main",
                    "label": "main",
                    "children": [
                        {
                            "id": "cat1.main.users",
                            "label": "users",
                        },
                    ],
                },
            ],
        },
    ]
    result = _find_node(nodes, "cat1.main")
    assert result["label"] == "main"
    result2 = _find_node(nodes, "cat1.main.users")
    assert result2["label"] == "users"


def test_find_node_returns_none_for_missing():
    """_find_node should return None for missing nodes."""
    from app.pages.query import _find_node

    nodes = [
        {
            "id": "cat1",
            "label": "Cat 1",
            "children": [],
        }
    ]
    assert _find_node(nodes, "nonexistent") is None


def test_find_node_empty_list():
    """_find_node should handle empty node list."""
    from app.pages.query import _find_node

    assert _find_node([], "anything") is None


def test_render_results_is_importable():
    """_render_results helper should be importable."""
    from app.pages.query import _render_results

    assert callable(_render_results)
