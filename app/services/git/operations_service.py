"""Service that performs git operations on workspace-relative repository folders."""

from __future__ import annotations

import logging
from pathlib import Path

import git as gitpython
from git import InvalidGitRepositoryError, Repo

from app.config import WORKSPACE_PATH
from app.services.git.models import ChangedFile, GitStatus

_log = logging.getLogger(__name__)


class GitOperationsService:
    """Performs git operations (status, diff, branch, commit, push, pull) on a folder.

    All methods accept a workspace-relative path to the git folder. The service
    resolves it against the configured WORKSPACE_PATH at call time so it can be
    used as a singleton or instantiated per-request.
    """

    def __init__(self, workspace_root: str = WORKSPACE_PATH) -> None:
        self._root = Path(workspace_root).resolve()

    def get_status(self, folder_path: str) -> GitStatus:
        """Return the current branch and all changed files in the repository."""
        repo = self._open_repo(folder_path)
        branch = self._current_branch(repo)
        files: list[ChangedFile] = []

        for item in repo.index.diff(None):
            files.append(ChangedFile(path=item.a_path, status="modified", is_staged=False))

        for item in repo.index.diff("HEAD"):
            files.append(ChangedFile(path=item.a_path, status=self._staged_status(item), is_staged=True))

        for item in repo.untracked_files:
            files.append(ChangedFile(path=item, status="untracked", is_staged=False))

        has_upstream = self._has_upstream(repo)
        return GitStatus(branch=branch, changed_files=files, has_upstream=has_upstream)

    def get_diff(self, folder_path: str, file_path: str) -> str:
        """Return the unified diff string for the given file."""
        repo = self._open_repo(folder_path)
        try:
            diff = repo.git.diff("HEAD", "--", file_path)
            if not diff:
                diff = repo.git.diff("--", file_path)
            if not diff:
                diff = repo.git.diff("--staged", "--", file_path)
            return diff or "(no diff available)"
        except Exception as exc:
            _log.warning("Could not get diff for '%s': %s", file_path, exc)
            return f"(error reading diff: {exc})"

    def list_branches(self, folder_path: str) -> list[str]:
        """Return all local and remote branch names, deduplicated and sorted."""
        repo = self._open_repo(folder_path)
        local = [head.name for head in repo.heads]
        remote = [
            ref.name.removeprefix("origin/")
            for ref in repo.remote().refs
            if not ref.name.endswith("/HEAD")
        ] if self._has_upstream(repo) else []
        return sorted(set(local + remote))

    def checkout_branch(self, folder_path: str, branch: str, create: bool = False) -> None:
        """Check out a branch, optionally creating it first."""
        repo = self._open_repo(folder_path)
        if create:
            repo.git.checkout("-b", branch)
        else:
            repo.git.checkout(branch)

    def discard_file(self, folder_path: str, file_path: str) -> None:
        """Revert a tracked file or remove an untracked file, discarding all changes."""
        repo = self._open_repo(folder_path)
        abs_path = self._root / folder_path / file_path
        if not abs_path.exists():
            repo.index.checkout([file_path], force=True)
        elif file_path in repo.untracked_files:
            abs_path.unlink(missing_ok=True)
        else:
            repo.index.checkout([file_path], force=True)

    def stage_files(self, folder_path: str, file_paths: list[str]) -> None:
        """Stage the specified files for commit."""
        repo = self._open_repo(folder_path)
        repo.index.add(file_paths)

    def commit_and_push(self, folder_path: str, message: str, file_paths: list[str]) -> None:
        """Stage the given files, commit with the provided message, then push.

        The push authenticates using the PAT stored for this folder's git connection,
        injected into the remote URL. Falls back to default credentials if no record exists.
        """
        if not message.strip():
            raise ValueError("Commit message must not be empty.")

        repo = self._open_repo(folder_path)
        repo.index.add(file_paths)
        repo.index.commit(message)

        if self._has_upstream(repo):
            self._push_with_auth(repo, folder_path)

    def pull(self, folder_path: str) -> None:
        """Pull the latest changes from the upstream remote."""
        repo = self._open_repo(folder_path)
        if not self._has_upstream(repo):
            raise ValueError("No remote configured for this repository.")
        self._pull_with_auth(repo, folder_path)

    def _open_repo(self, folder_path: str) -> Repo:
        full_path = self._root / folder_path
        try:
            return gitpython.Repo(str(full_path))
        except InvalidGitRepositoryError as exc:
            raise ValueError(f"'{folder_path}' is not a valid git repository.") from exc

    @staticmethod
    def _current_branch(repo: Repo) -> str:
        try:
            name: str = repo.active_branch.name
            return name
        except TypeError:
            sha: str = repo.head.commit.hexsha[:7]
            return sha

    @staticmethod
    def _has_upstream(repo: Repo) -> bool:
        try:
            return bool(repo.remotes)
        except Exception:
            return False

    @staticmethod
    def _staged_status(diff_item: gitpython.Diff) -> str:
        if diff_item.new_file:
            return "added"
        if diff_item.deleted_file:
            return "deleted"
        if diff_item.renamed_file:
            return "renamed"
        return "modified"

    def _push_with_auth(self, repo: Repo, folder_path: str) -> None:
        auth_url = self._build_authenticated_url(folder_path, repo)
        if auth_url:
            repo.git.push(auth_url, repo.active_branch.name)
        else:
            repo.remotes.origin.push()

    def _pull_with_auth(self, repo: Repo, folder_path: str) -> None:
        auth_url = self._build_authenticated_url(folder_path, repo)
        if auth_url:
            repo.git.pull(auth_url, repo.active_branch.name)
        else:
            repo.remotes.origin.pull()

    def _build_authenticated_url(self, folder_path: str, repo: Repo) -> str | None:
        """Look up the stored PAT for this folder and inject it into the remote URL."""
        try:
            from app.services.database.session import get_session  # noqa: PLC0415
            from app.services.database.models.app import GitFolder  # noqa: PLC0415
            from app.services.git.connection_service import GitConnectionService  # noqa: PLC0415
            from app.services.git.encryption import TokenEncryptor  # noqa: PLC0415

            with get_session() as session:
                record: GitFolder | None = (
                    session.query(GitFolder).filter_by(workspace_path=folder_path).first()
                )
                if record is None:
                    return None
                connection_id = record.git_connection_id

            connection_service = GitConnectionService()
            connection = connection_service.get(connection_id)
            token = TokenEncryptor.decrypt(connection.token_encrypted)

            origin_url: str = repo.remotes.origin.url
            if origin_url.startswith("https://"):
                return origin_url.replace("https://", f"https://oauth2:{token}@", 1)
            return None
        except Exception as exc:
            _log.debug("Could not build authenticated URL for '%s': %s", folder_path, exc)
            return None
