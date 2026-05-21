"""Unit tests for QueryTabService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.query.tab_service import QueryTabService


def _make_tab(tab_id: int, name: str, sql_content: str = "", position: int = 0):
    tab = MagicMock()
    tab.id = tab_id
    tab.name = name
    tab.sql_content = sql_content
    tab.position = position
    return tab


def _mock_session():
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


class TestEnsureDefault:
    def test_returns_first_tab_when_tabs_exist(self):
        service = QueryTabService()
        tab = _make_tab(1, "Query 1")

        with patch.object(service, "list_tabs", return_value=[tab]):
            result = service.ensure_default()

        assert result is tab

    def test_creates_default_tab_when_none_exist(self):
        service = QueryTabService()
        new_tab = _make_tab(1, "Query 1")

        with (
            patch.object(service, "list_tabs", return_value=[]),
            patch.object(service, "create_tab", return_value=new_tab) as mock_create,
        ):
            result = service.ensure_default()

        mock_create.assert_called_once_with("Query 1")
        assert result is new_tab


class TestListTabs:
    def test_returns_empty_list_when_no_tabs(self):
        service = QueryTabService()
        session = _mock_session()
        session.query.return_value.order_by.return_value.all.return_value = []

        with patch("app.services.query.tab_service.get_session", return_value=session):
            result = service.list_tabs()

        assert result == []

    def test_returns_tabs_ordered(self):
        service = QueryTabService()
        tab1 = _make_tab(1, "Query 1", position=0)
        tab2 = _make_tab(2, "Query 2", position=1)
        session = _mock_session()
        session.query.return_value.order_by.return_value.all.return_value = [tab1, tab2]

        with patch("app.services.query.tab_service.get_session", return_value=session):
            result = service.list_tabs()

        assert result == [tab1, tab2]


class TestCreateTab:
    def test_creates_tab_with_name_and_content(self):
        service = QueryTabService()
        session = _mock_session()
        session.query.return_value.count.return_value = 0

        created_tab = _make_tab(1, "My Query", "SELECT 1")
        session.query.return_value.count.return_value = 0

        def fake_refresh(tab):
            tab.id = 1

        session.refresh.side_effect = fake_refresh

        with (
            patch("app.services.query.tab_service.get_session", return_value=session),
            patch(
                "app.services.query.tab_service.QueryTab",
                return_value=created_tab,
            ),
        ):
            result = service.create_tab("My Query", "SELECT 1")

        session.add.assert_called_once_with(created_tab)
        session.flush.assert_called_once()

    def test_position_equals_existing_count(self):
        service = QueryTabService()
        session = _mock_session()
        session.query.return_value.count.return_value = 3

        captured = {}

        def fake_tab(**kwargs):
            captured.update(kwargs)
            return _make_tab(4, kwargs["name"])

        with (
            patch("app.services.query.tab_service.get_session", return_value=session),
            patch("app.services.query.tab_service.QueryTab", side_effect=fake_tab),
        ):
            service.create_tab("Query 4")

        assert captured["position"] == 3


class TestUpdateContent:
    def test_updates_sql_content(self):
        service = QueryTabService()
        tab = _make_tab(1, "Query 1", "OLD SQL")
        session = _mock_session()
        session.query.return_value.filter_by.return_value.first.return_value = tab

        with patch("app.services.query.tab_service.get_session", return_value=session):
            service.update_content(1, "SELECT 2")

        assert tab.sql_content == "SELECT 2"

    def test_raises_when_tab_not_found(self):
        service = QueryTabService()
        session = _mock_session()
        session.query.return_value.filter_by.return_value.first.return_value = None

        with (
            patch("app.services.query.tab_service.get_session", return_value=session),
            pytest.raises(ValueError, match="not found"),
        ):
            service.update_content(999, "SELECT 1")


class TestRenameTab:
    def test_renames_tab(self):
        service = QueryTabService()
        tab = _make_tab(1, "Old Name")
        session = _mock_session()
        session.query.return_value.filter_by.return_value.first.return_value = tab

        with patch("app.services.query.tab_service.get_session", return_value=session):
            service.rename_tab(1, "New Name")

        assert tab.name == "New Name"

    def test_strips_whitespace(self):
        service = QueryTabService()
        tab = _make_tab(1, "Old")
        session = _mock_session()
        session.query.return_value.filter_by.return_value.first.return_value = tab

        with patch("app.services.query.tab_service.get_session", return_value=session):
            service.rename_tab(1, "  Trimmed  ")

        assert tab.name == "Trimmed"

    def test_raises_on_empty_name(self):
        service = QueryTabService()
        with pytest.raises(ValueError, match="empty"):
            service.rename_tab(1, "   ")

    def test_raises_when_tab_not_found(self):
        service = QueryTabService()
        session = _mock_session()
        session.query.return_value.filter_by.return_value.first.return_value = None

        with (
            patch("app.services.query.tab_service.get_session", return_value=session),
            pytest.raises(ValueError, match="not found"),
        ):
            service.rename_tab(999, "New Name")


class TestDeleteTab:
    def test_deletes_tab_when_multiple_exist(self):
        service = QueryTabService()
        tab = _make_tab(2, "Query 2")
        session = _mock_session()
        session.query.return_value.count.return_value = 3
        session.query.return_value.filter_by.return_value.first.return_value = tab

        with patch("app.services.query.tab_service.get_session", return_value=session):
            service.delete_tab(2)

        session.delete.assert_called_once_with(tab)

    def test_raises_when_only_one_tab_remains(self):
        service = QueryTabService()
        session = _mock_session()
        session.query.return_value.count.return_value = 1

        with (
            patch("app.services.query.tab_service.get_session", return_value=session),
            pytest.raises(ValueError, match="last"),
        ):
            service.delete_tab(1)

    def test_raises_when_tab_not_found(self):
        service = QueryTabService()
        session = _mock_session()
        session.query.return_value.count.return_value = 3
        session.query.return_value.filter_by.return_value.first.return_value = None

        with (
            patch("app.services.query.tab_service.get_session", return_value=session),
            pytest.raises(ValueError, match="not found"),
        ):
            service.delete_tab(999)
