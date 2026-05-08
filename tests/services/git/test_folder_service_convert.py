"""Unit tests for GitFolderService.convert_to_git."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import git as gitpython
import pytest

from app.services.git.folder_service import GitFolderService


class TestConvertToGit:
    def _make_service(self, tmp_path: Path) -> GitFolderService:
        return GitFolderService(str(tmp_path))

    def _mock_session(self):
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        return session

    def test_raises_if_folder_does_not_exist(self, tmp_path):
        service = self._make_service(tmp_path)
        with pytest.raises(ValueError, match="does not exist"):
            service.convert_to_git("nonexistent", 1, "https://github.com/u/r", "main")

    def test_raises_if_already_git_repo(self, tmp_path):
        existing = tmp_path / "my-repo"
        existing.mkdir()
        service = self._make_service(tmp_path)

        mock_repo = MagicMock()
        with (
            patch("app.services.git.folder_service.gitpython.Repo", return_value=mock_repo),
            pytest.raises(ValueError, match="already a git repository"),
        ):
            service.convert_to_git("my-repo", 1, "https://github.com/u/r", "main")

    def test_raises_if_remote_is_not_empty(self, tmp_path):
        folder = tmp_path / "project"
        folder.mkdir()
        service = self._make_service(tmp_path)

        mock_provider = MagicMock()
        mock_provider.build_authenticated_url.return_value = "https://token@github.com/u/r"

        mock_git_cls = MagicMock()
        mock_git_cls.return_value.ls_remote.return_value = "abc123\trefs/heads/main\n"

        with (
            patch(
                "app.services.git.folder_service.gitpython.Repo",
                side_effect=gitpython.InvalidGitRepositoryError,
            ),
            patch("app.services.git.folder_service._git_connection_service.get"),
            patch(
                "app.services.git.folder_service._git_connection_service.build_provider",
                return_value=mock_provider,
            ),
            patch("app.services.git.folder_service.gitpython.Git", mock_git_cls),
            pytest.raises(ValueError, match="not empty"),
        ):
            service.convert_to_git("project", 1, "https://github.com/u/r", "main")

    def test_raises_if_remote_unreachable(self, tmp_path):
        folder = tmp_path / "project"
        folder.mkdir()
        service = self._make_service(tmp_path)

        mock_provider = MagicMock()
        mock_provider.build_authenticated_url.return_value = "https://bad@github.com/u/r"

        mock_git_cls = MagicMock()
        mock_git_cls.return_value.ls_remote.side_effect = Exception("connection refused")

        with (
            patch(
                "app.services.git.folder_service.gitpython.Repo",
                side_effect=gitpython.InvalidGitRepositoryError,
            ),
            patch("app.services.git.folder_service._git_connection_service.get"),
            patch(
                "app.services.git.folder_service._git_connection_service.build_provider",
                return_value=mock_provider,
            ),
            patch("app.services.git.folder_service.gitpython.Git", mock_git_cls),
            pytest.raises(ValueError, match="Could not reach remote"),
        ):
            service.convert_to_git("project", 1, "https://github.com/u/r", "main")

    def test_successful_conversion(self, tmp_path):
        folder = tmp_path / "project"
        folder.mkdir()
        service = self._make_service(tmp_path)

        mock_provider = MagicMock()
        mock_provider.build_authenticated_url.return_value = "https://token@github.com/u/r"

        mock_git_cls = MagicMock()
        mock_git_cls.return_value.ls_remote.return_value = ""

        mock_repo_instance = MagicMock()
        mock_repo_init = MagicMock(return_value=mock_repo_instance)

        mock_session = self._mock_session()

        with (
            patch(
                "app.services.git.folder_service.gitpython.Repo",
                side_effect=gitpython.InvalidGitRepositoryError,
            ),
            patch("app.services.git.folder_service.gitpython.Repo.init", mock_repo_init),
            patch("app.services.git.folder_service._git_connection_service.get"),
            patch(
                "app.services.git.folder_service._git_connection_service.build_provider",
                return_value=mock_provider,
            ),
            patch("app.services.git.folder_service.gitpython.Git", mock_git_cls),
            patch("app.services.git.folder_service.get_session", return_value=mock_session),
        ):
            service.convert_to_git("project", 2, "https://github.com/u/r", "main")

        mock_repo_init.assert_called_once_with(str(folder))
        mock_repo_instance.git.symbolic_ref.assert_called_once_with("HEAD", "refs/heads/main")
        mock_repo_instance.git.remote.assert_called_once_with(
            "add", "origin", "https://github.com/u/r"
        )
        mock_repo_instance.git.add.assert_called_once_with("-A")
        mock_repo_instance.git.commit.assert_called_once_with(
            "--allow-empty", "-m", "Initial commit"
        )
        mock_repo_instance.git.push.assert_called_once_with(
            "https://token@github.com/u/r", "main:main"
        )
        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.workspace_path == "project"
        assert added.git_connection_id == 2
        assert added.repo_url == "https://github.com/u/r"
        assert added.branch == "main"
