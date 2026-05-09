"""Tests for GitOperationsService using an in-memory git repository."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from git import GitCommandError

from app.services.git.models import ChangedFile, GitAuthError, GitStatus
from app.services.git.operations_service import GitOperationsService


def _make_diff_item(
    path: str = "file.py",
    *,
    new_file: bool = False,
    deleted_file: bool = False,
    renamed_file: bool = False,
) -> MagicMock:
    item = MagicMock()
    item.a_path = path
    item.new_file = new_file
    item.deleted_file = deleted_file
    item.renamed_file = renamed_file
    return item


@pytest.fixture()
def mock_repo(tmp_path: Path):
    """Return a GitOperationsService backed by a mocked gitpython Repo."""
    service = GitOperationsService(workspace_root=str(tmp_path))

    repo = MagicMock()
    repo.active_branch.name = "main"
    repo.remotes = []
    repo.untracked_files = []
    repo.heads = [MagicMock(name="main")]
    repo.index.diff.return_value = []
    repo.index.diff.side_effect = None

    with patch.object(service, "_open_repo", return_value=repo):
        yield service, repo, tmp_path


class TestGetStatus:
    def test_returns_git_status_with_branch(self, mock_repo):
        service, repo, _ = mock_repo
        repo.index.diff.return_value = []
        repo.untracked_files = []

        status = service.get_status("repo")

        assert isinstance(status, GitStatus)
        assert status.branch == "main"
        assert status.changed_files == []

    def test_collects_unstaged_modified_files(self, mock_repo):
        service, repo, _ = mock_repo
        unstaged = _make_diff_item("src/app.py")

        def diff_side_effect(target):
            if target is None:
                return [unstaged]
            return []

        repo.index.diff.side_effect = diff_side_effect
        repo.untracked_files = []

        status = service.get_status("repo")

        assert len(status.changed_files) == 1
        assert status.changed_files[0].path == "src/app.py"
        assert status.changed_files[0].status == "modified"
        assert not status.changed_files[0].is_staged

    def test_collects_staged_added_files(self, mock_repo):
        service, repo, _ = mock_repo
        staged = _make_diff_item("new_file.py", new_file=True)

        def diff_side_effect(target):
            if target == "HEAD":
                return [staged]
            return []

        repo.index.diff.side_effect = diff_side_effect
        repo.untracked_files = []

        status = service.get_status("repo")

        staged_files = [f for f in status.changed_files if f.is_staged]
        assert len(staged_files) == 1
        assert staged_files[0].status == "added"

    def test_collects_untracked_files(self, mock_repo):
        service, repo, _ = mock_repo
        repo.index.diff.return_value = []
        repo.index.diff.side_effect = lambda _: []
        repo.untracked_files = ["scratch.py"]

        status = service.get_status("repo")

        untracked = [f for f in status.changed_files if f.status == "untracked"]
        assert len(untracked) == 1
        assert untracked[0].path == "scratch.py"
        assert not untracked[0].is_staged


class TestGetDiff:
    def test_returns_git_diff_output(self, mock_repo):
        service, repo, _ = mock_repo
        repo.git.diff.return_value = "@@ -1,2 +1,3 @@\n+new line\n context"

        result = service.get_diff("repo", "file.py")

        assert "@@ -1,2 +1,3 @@" in result

    def test_returns_placeholder_on_error(self, mock_repo):
        service, repo, _ = mock_repo
        repo.git.diff.side_effect = Exception("boom")

        result = service.get_diff("repo", "file.py")

        assert "error" in result.lower()


class TestListBranches:
    def test_returns_sorted_unique_branches(self, mock_repo):
        service, repo, _ = mock_repo

        local_head = MagicMock()
        local_head.name = "main"
        repo.heads = [local_head]

        remote_ref_main = MagicMock()
        remote_ref_main.name = "origin/main"
        remote_ref_feat = MagicMock()
        remote_ref_feat.name = "origin/feature-x"

        remote = MagicMock()
        remote.refs = [remote_ref_main, remote_ref_feat]
        repo.remotes = [remote]
        repo.remote.return_value = remote

        branches = service.list_branches("repo")

        assert "main" in branches
        assert "feature-x" in branches
        assert branches == sorted(set(branches))

    def test_returns_only_local_when_no_remote(self, mock_repo):
        service, repo, _ = mock_repo
        local_head = MagicMock()
        local_head.name = "dev"
        repo.heads = [local_head]
        repo.remotes = []

        branches = service.list_branches("repo")

        assert branches == ["dev"]


class TestCheckoutBranch:
    def test_checks_out_existing_branch(self, mock_repo):
        service, repo, _ = mock_repo

        service.checkout_branch("repo", "feature-x")

        repo.git.checkout.assert_called_once_with("feature-x")

    def test_creates_new_branch(self, mock_repo):
        service, repo, _ = mock_repo

        service.checkout_branch("repo", "new-branch", create=True)

        repo.git.checkout.assert_called_once_with("-b", "new-branch")


class TestDiscardFile:
    def test_discards_tracked_file(self, mock_repo, tmp_path):
        service, repo, base = mock_repo
        tracked = tmp_path / "repo" / "file.py"
        tracked.parent.mkdir(parents=True, exist_ok=True)
        tracked.write_text("content")
        repo.untracked_files = []

        service.discard_file("repo", "file.py")

        repo.index.checkout.assert_called_once_with(["file.py"], force=True)

    def test_deletes_untracked_file(self, mock_repo, tmp_path):
        service, repo, base = mock_repo
        untracked = tmp_path / "repo" / "scratch.py"
        untracked.parent.mkdir(parents=True, exist_ok=True)
        untracked.write_text("junk")
        repo.untracked_files = ["scratch.py"]

        service.discard_file("repo", "scratch.py")

        assert not untracked.exists()


class TestCommitAndPush:
    def test_raises_on_empty_message(self, mock_repo):
        service, _, _ = mock_repo
        with pytest.raises(ValueError, match="Commit message"):
            service.commit_and_push("repo", "   ", ["file.py"])

    def test_stages_commits_without_push_if_no_remote(self, mock_repo):
        service, repo, _ = mock_repo
        repo.remotes = []

        service.commit_and_push("repo", "fix: small fix", ["file.py"])

        repo.git.add.assert_called_once_with(["file.py"])
        repo.index.commit.assert_called_once_with("fix: small fix")

    def test_stages_deleted_file_without_error(self, mock_repo):
        """Deleted files must be stageable via git.add without FileNotFoundError."""
        service, repo, _ = mock_repo
        repo.remotes = []

        service.commit_and_push("repo", "fix: remove old file", ["deleted_file.py"])

        repo.git.add.assert_called_once_with(["deleted_file.py"])
        repo.index.commit.assert_called_once_with("fix: remove old file")


class TestChangedFileModel:
    def test_status_label_mapping(self):
        assert ChangedFile("f.py", "modified", False).status_label == "M"
        assert ChangedFile("f.py", "added", True).status_label == "A"
        assert ChangedFile("f.py", "deleted", False).status_label == "D"
        assert ChangedFile("f.py", "untracked", False).status_label == "U"
        assert ChangedFile("f.py", "renamed", True).status_label == "R"

    def test_status_color_returns_string(self):
        for status in ("modified", "added", "deleted", "untracked", "renamed"):
            color = ChangedFile("f.py", status, False).status_color
            assert isinstance(color, str)
            assert color  # non-empty


class TestBuildAuthenticatedUrl:
    """Verify that credential injection never produces double-credential URLs."""

    def test_injects_token_into_clean_url(self):
        result = GitOperationsService._inject_token("https://github.com/user/repo.git", "TOKEN123")
        assert result == "https://oauth2:TOKEN123@github.com/user/repo.git"

    def test_replaces_existing_credentials_without_doubling(self):
        result = GitOperationsService._inject_token(
            "https://oauth2:OLD_TOKEN@github.com/user/repo.git", "NEW_TOKEN"
        )
        assert result is not None
        assert result.count("@") == 1, "URL must contain exactly one @ separator"
        assert "NEW_TOKEN" in result
        assert "OLD_TOKEN" not in result

    def test_returns_none_for_ssh_url(self):
        result = GitOperationsService._inject_token("git@github.com:user/repo.git", "TOKEN")
        assert result is None

    def test_preserves_path(self):
        result = GitOperationsService._inject_token("https://github.com/org/my-repo.git", "ABC")
        assert result is not None
        assert "/org/my-repo.git" in result


class TestClassifyGitError:
    def _make_cmd_error(self, status: int, stderr: str) -> GitCommandError:
        err = GitCommandError(["git", "push"], status)
        err.stderr = stderr
        return err

    def test_auth_failure_returns_git_auth_error(self):
        exc = self._make_cmd_error(128, "fatal: Authentication failed for 'https://github.com/'")
        result = GitOperationsService._classify_git_error(exc)
        assert isinstance(result, GitAuthError)

    def test_non_auth_exit_128_returns_original(self):
        exc = self._make_cmd_error(128, "fatal: repository not found")
        result = GitOperationsService._classify_git_error(exc)
        assert result is exc

    def test_non_128_exit_code_returns_original(self):
        exc = self._make_cmd_error(1, "Authentication failed")
        result = GitOperationsService._classify_git_error(exc)
        assert result is exc

    def test_push_raises_git_auth_error_on_auth_failure(self, mock_repo):
        service, repo, _ = mock_repo
        repo.remotes = [MagicMock()]

        auth_exc = GitCommandError(["git", "push"], 128)
        auth_exc.stderr = "fatal: Authentication failed for 'https://github.com/'"

        with patch.object(
            service, "_build_authenticated_url", return_value="https://oauth2:t@github.com/r.git"
        ):
            repo.git.push.side_effect = auth_exc
            with pytest.raises(GitAuthError):
                service.commit_and_push("repo", "fix: auth", ["file.py"])

    def test_pull_raises_git_auth_error_on_auth_failure(self, mock_repo):
        service, repo, _ = mock_repo
        repo.remotes = [MagicMock()]

        auth_exc = GitCommandError(["git", "pull"], 128)
        auth_exc.stderr = "fatal: Authentication failed for 'https://github.com/'"

        with patch.object(
            service, "_build_authenticated_url", return_value="https://oauth2:t@github.com/r.git"
        ):
            repo.git.pull.side_effect = auth_exc
            with pytest.raises(GitAuthError):
                service.pull("repo")
