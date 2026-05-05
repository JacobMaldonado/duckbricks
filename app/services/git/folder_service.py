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
