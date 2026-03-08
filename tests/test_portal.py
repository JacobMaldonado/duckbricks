"""Tests for the Basic Portal."""


def test_layout_frame_is_importable():
    """layout_frame should be importable."""
    from app.components.layout import layout_frame

    assert callable(layout_frame)


def test_explorer_page_is_importable():
    """explorer_page should be importable."""
    from app.pages.explorer import explorer_page

    assert callable(explorer_page)


def test_query_workspace_is_importable():
    """query_workspace should be importable."""
    from app.pages.query import query_workspace

    assert callable(query_workspace)
