"""Service for creating and managing git-tracked workspace folders."""

from __future__ import annotations

import logging
from pathlib import Path

import git as gitpython

from app.services.database.models.app import GitFolder
from app.services.database.session import get_session
from app.services.git.connection_service import GitConnectionService

_log = logging.getLogger(__name__)

_git_connection_service = GitConnectionService()


class GitFolderService:
    """Clones repositories into the workspace and tracks them in the database."""

    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def create(
        self,
        folder_name: str,
        git_connection_id: int,
        repo_url: str,
        branch: str,
    ) -> GitFolder:
        """Clone a repository and register the folder in the database.

        The folder is cloned at workspace_root / folder_name. An existing
        directory at that path is treated as an error to avoid data loss.
        """
        destination = self._workspace_root / folder_name
        if destination.exists():
            raise ValueError(f"Folder '{folder_name}' already exists in the workspace.")

        connection = _git_connection_service.get(git_connection_id)
        provider = _git_connection_service.build_provider(connection)
        provider.clone(repo_url, str(destination), branch)

        workspace_path = folder_name
        with get_session() as session:
            git_folder = GitFolder(
                workspace_path=workspace_path,
                git_connection_id=git_connection_id,
                repo_url=repo_url,
                branch=branch,
            )
            session.add(git_folder)
            session.flush()
            session.refresh(git_folder)
            session.expunge(git_folder)
            return git_folder

    def list_all(self) -> list[GitFolder]:
        """Return all registered git folders."""
        with get_session() as session:
            folders: list[GitFolder] = session.query(GitFolder).all()
            for f in folders:
                session.expunge(f)
            return folders

    def delete(self, folder_id: int) -> None:
        """Remove the database record for a git folder (does not delete files)."""
        with get_session() as session:
            folder = session.query(GitFolder).filter_by(id=folder_id).first()
            if folder is None:
                raise ValueError(f"GitFolder {folder_id} not found.")
            session.delete(folder)

    def get_tracked_paths(self) -> set[str]:
        """Return workspace-relative paths of all registered git folders."""
        return {f.workspace_path for f in self.list_all()}

    def get_active_branch(self, workspace_path: str) -> str | None:
        """Return the currently checked-out branch for a workspace path, or None."""
        full_path = self._workspace_root / workspace_path
        try:
            repo = gitpython.Repo(str(full_path))
            branch: str = repo.active_branch.name
            return branch
        except Exception as exc:
            _log.debug("Could not read branch for '%s': %s", workspace_path, exc)
            return None

    def is_token_expired(self, workspace_path: str) -> bool:
        """Return True if the connection backing this folder has an invalid token."""
        with get_session() as session:
            folder = session.query(GitFolder).filter_by(workspace_path=workspace_path).first()
            if folder is None:
                return False
            connection_id = folder.git_connection_id
        return not _git_connection_service.test_connection(connection_id)

    def register_or_reassign(self, workspace_path: str, connection_id: int) -> None:
        """Link a folder to the given connection, creating the DB record if necessary.

        If the folder is already registered, its connection is updated in place.
        If it is not registered yet (e.g. cloned outside DuckBricks or after a DB
        reset), the method reads the repo URL and active branch from disk and
        inserts a new ``GitFolder`` record automatically.
        """
        with get_session() as session:
            folder = session.query(GitFolder).filter_by(workspace_path=workspace_path).first()
            if folder is not None:
                folder.git_connection_id = connection_id
                return

            full_path = self._workspace_root / workspace_path
            try:
                repo = gitpython.Repo(str(full_path))
                repo_url = self._strip_credentials_from_url(repo.remotes.origin.url)
                branch = repo.active_branch.name
            except Exception as exc:
                raise ValueError(
                    f"Cannot register '{workspace_path}': not a valid git repository — {exc}"
                ) from exc

            session.add(
                GitFolder(
                    workspace_path=workspace_path,
                    git_connection_id=connection_id,
                    repo_url=repo_url,
                    branch=branch,
                )
            )

    @staticmethod
    def _strip_credentials_from_url(raw_url: str) -> str:
        """Return the URL with any embedded username/token removed."""
        from urllib.parse import urlparse  # noqa: PLC0415

        parsed = urlparse(raw_url)
        if not parsed.hostname:
            return raw_url
        host_with_port = f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname
        return parsed._replace(netloc=host_with_port).geturl()

    def get_connection_id(self, workspace_path: str) -> int | None:
        """Return the git_connection_id for a workspace folder, or None."""
        with get_session() as session:
            folder = session.query(GitFolder).filter_by(workspace_path=workspace_path).first()
            if folder is None:
                return None
            return int(folder.git_connection_id)

    def convert_to_git(
        self,
        folder_path: str,
        connection_id: int,
        repo_url: str,
        branch: str,
    ) -> None:
        """Initialise a workspace folder as a git repo and push it to an empty remote.

        The method validates that:
        - The folder exists on disk.
        - The folder is **not** already a git repository.
        - The remote repository is **empty** (no refs/commits).

        On success the folder is committed, pushed, and registered in the DB.
        """
        full_path = self._workspace_root / folder_path
        if not full_path.is_dir():
            raise ValueError(f"Folder '{folder_path}' does not exist in the workspace.")

        self._assert_not_already_git_repo(full_path)

        connection = _git_connection_service.get(connection_id)
        provider = _git_connection_service.build_provider(connection)
        auth_url = provider.build_authenticated_url(repo_url)

        self._assert_remote_is_empty(auth_url, folder_path)

        repo = gitpython.Repo.init(str(full_path))
        repo.git.symbolic_ref("HEAD", f"refs/heads/{branch}")
        repo.git.remote("add", "origin", repo_url)
        repo.git.add("-A")
        repo.git.commit("--allow-empty", "-m", "Initial commit")
        repo.git.push(auth_url, f"{branch}:{branch}")

        with get_session() as session:
            session.add(
                GitFolder(
                    workspace_path=folder_path,
                    git_connection_id=connection_id,
                    repo_url=repo_url,
                    branch=branch,
                )
            )

    @staticmethod
    def _assert_not_already_git_repo(full_path: Path) -> None:
        """Raise ValueError if the path is already a git repository."""
        try:
            gitpython.Repo(str(full_path))
            raise ValueError(f"Folder '{full_path.name}' is already a git repository.")
        except gitpython.InvalidGitRepositoryError:
            pass

    @staticmethod
    def _assert_remote_is_empty(auth_url: str, folder_path: str) -> None:
        """Raise ValueError if the remote already contains commits or branches."""
        try:
            remote_refs = gitpython.Git().ls_remote(auth_url)
        except Exception as exc:
            raise ValueError(f"Could not reach remote for '{folder_path}': {exc}") from exc
        if remote_refs.strip():
            raise ValueError(
                "Remote repository is not empty. " "Please use a fresh repository with no commits."
            )
