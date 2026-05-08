"""Tests for GitConnectionService.update_token and GitFolderService.reassign_connection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.git.connection_service import GitConnectionService
from app.services.git.folder_service import GitFolderService


class TestUpdateToken:
    def test_encrypts_and_saves_new_token(self):
        service = GitConnectionService()

        mock_connection = MagicMock()
        mock_connection.id = 1

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_connection

        with (
            patch("app.services.git.connection_service.get_session", return_value=mock_session),
            patch(
                "app.services.git.connection_service.TokenEncryptor.encrypt",
                return_value=b"encrypted",
            ) as mock_encrypt,
        ):
            service.update_token(1, "new-pat-token")

        mock_encrypt.assert_called_once_with("new-pat-token")
        assert mock_connection.token_encrypted == b"encrypted"

    def test_raises_if_connection_not_found(self):
        service = GitConnectionService()

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        with (
            patch("app.services.git.connection_service.get_session", return_value=mock_session),
            pytest.raises(ValueError, match="GitConnection 99 not found"),
        ):
            service.update_token(99, "token")


class TestReassignConnection:
    def _make_service(self, tmp_path) -> GitFolderService:
        return GitFolderService(str(tmp_path))

    def test_updates_git_connection_id(self, tmp_path):
        service = self._make_service(tmp_path)

        mock_folder = MagicMock()
        mock_folder.git_connection_id = 1

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_folder

        with patch("app.services.git.folder_service.get_session", return_value=mock_session):
            service.reassign_connection("my-repo", 2)

        assert mock_folder.git_connection_id == 2

    def test_raises_if_folder_not_found(self, tmp_path):
        service = self._make_service(tmp_path)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        with (
            patch("app.services.git.folder_service.get_session", return_value=mock_session),
            pytest.raises(ValueError, match="No git folder registered"),
        ):
            service.reassign_connection("missing", 5)


class TestGetConnectionId:
    def _make_service(self, tmp_path) -> GitFolderService:
        return GitFolderService(str(tmp_path))

    def test_returns_connection_id_when_found(self, tmp_path):
        service = self._make_service(tmp_path)

        mock_folder = MagicMock()
        mock_folder.git_connection_id = 7

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_folder

        with patch("app.services.git.folder_service.get_session", return_value=mock_session):
            result = service.get_connection_id("my-repo")

        assert result == 7

    def test_returns_none_when_folder_missing(self, tmp_path):
        service = self._make_service(tmp_path)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        with patch("app.services.git.folder_service.get_session", return_value=mock_session):
            result = service.get_connection_id("missing")

        assert result is None
