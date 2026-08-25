"""Contract tests for the selected Metastore Workbench."""

from app.ui.components.metastore_workbench import (
    METASTORE_WORKBENCH_CSS,
    QUALITY_ICON,
    MetastoreWorkbench,
)
from app.ui.components.navigation import NAVIGATION_DESTINATIONS


def test_workbench_has_responsive_three_pane_layout() -> None:
    assert "grid-template-columns: 250px 310px minmax(0, 1fr)" in METASTORE_WORKBENCH_CSS
    assert "@media (max-width: 850px)" in METASTORE_WORKBENCH_CSS
    assert "flex-direction: column" in METASTORE_WORKBENCH_CSS


def test_metric_icons_have_a_fixed_alignment_box() -> None:
    assert ".metastore-workbench-metric-icon" in METASTORE_WORKBENCH_CSS
    assert "align-items: center" in METASTORE_WORKBENCH_CSS
    assert QUALITY_ICON == "verified"


def test_workbench_formats_live_values_without_inventing_metrics() -> None:
    assert MetastoreWorkbench._format_count(None) == "—"
    assert MetastoreWorkbench._format_count(1234) == "1,234"
    assert MetastoreWorkbench._format_bytes(None) == "Not applicable"
    assert MetastoreWorkbench._format_bytes(2048) == "2.0 KB"


def test_navigation_contains_only_the_selected_metastore_page() -> None:
    metastore_destinations = [
        destination
        for destination in NAVIGATION_DESTINATIONS
        if destination.route in {"/explorer", "/metastore-lab"}
    ]

    assert len(metastore_destinations) == 1
    assert metastore_destinations[0].route == "/explorer"
    assert metastore_destinations[0].label == "Metastore"
