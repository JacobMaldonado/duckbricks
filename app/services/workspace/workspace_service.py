"""Workspace service — CRUD operations over the shared file workspace."""

from __future__ import annotations

import shutil
from pathlib import Path


class WorkspaceNode:
    """Represents a file or folder entry in the workspace tree."""

    def __init__(
        self,
        name: str,
        path: str,
        is_dir: bool,
        children: list[WorkspaceNode] | None = None,
        is_git_folder: bool = False,
        git_branch: str | None = None,
    ) -> None:
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.children: list[WorkspaceNode] = children or []
        self.is_git_folder = is_git_folder
        self.git_branch = git_branch

    def __repr__(self) -> str:
        kind = "git-dir" if self.is_git_folder else ("dir" if self.is_dir else "file")
        return f"WorkspaceNode({kind}, {self.path!r})"


class WorkspaceService:
    """Provides file and folder management for the DuckBricks shared workspace."""

    ALLOWED_EXTENSIONS = {".sql", ".py", ".ipynb", ".txt", ".md"}

    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def list_tree(self, git_tracked_paths: set[str] | None = None) -> list[WorkspaceNode]:
        """Return a recursive tree of WorkspaceNodes rooted at the workspace directory.

        When git_tracked_paths is provided, directories whose workspace-relative
        path is in that set are annotated as git folders.
        """
        return self._build_tree(self._root, git_tracked_paths or set())

    def list_files(self, extensions: list[str] | None = None) -> list[str]:
        """Return absolute paths for all files in the workspace, filtered by extension."""
        result: list[str] = []
        for path in sorted(self._root.rglob("*")):
            if path.is_file() and path.name != ".git":
                if extensions is None or path.suffix.lstrip(".") in extensions:
                    result.append(str(path))
        return result

    def read_file(self, relative_path: str) -> str:
        """Read and return the content of a workspace file."""
        full_path = self._resolve_safe(relative_path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        return full_path.read_text(encoding="utf-8")

    def write_file(self, relative_path: str, content: str) -> None:
        """Write content to a workspace file, creating parent directories as needed."""
        full_path = self._resolve_safe(relative_path)
        if full_path.suffix not in self.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Extension '{full_path.suffix}' is not allowed. "
                f"Allowed: {sorted(self.ALLOWED_EXTENSIONS)}"
            )
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    def create_folder(self, relative_path: str) -> None:
        """Create a folder (and any missing parents) within the workspace."""
        full_path = self._resolve_safe(relative_path)
        full_path.mkdir(parents=True, exist_ok=True)

    def delete(self, relative_path: str) -> None:
        """Delete a file or folder (recursively) from the workspace."""
        full_path = self._resolve_safe(relative_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Path not found: {relative_path}")
        if full_path.is_dir():
            shutil.rmtree(full_path)
        else:
            full_path.unlink()

    def rename(self, relative_path: str, new_name: str) -> str:
        """Rename a file or folder inside its parent directory. Returns the new relative path."""
        full_path = self._resolve_safe(relative_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Path not found: {relative_path}")
        new_full_path = full_path.parent / new_name
        full_path.rename(new_full_path)
        return str(new_full_path.relative_to(self._root))

    def clone(self, relative_path: str) -> str:
        """Clone a file or folder to a new name in the same parent directory."""
        full_path = self._resolve_safe(relative_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Path not found: {relative_path}")
        parent = full_path.parent
        stem = full_path.stem if full_path.is_file() else full_path.name
        suffix = full_path.suffix if full_path.is_file() else ""
        candidate = parent / f"{stem}_copy{suffix}"
        counter = 1
        while candidate.exists():
            candidate = parent / f"{stem}_copy{counter}{suffix}"
            counter += 1
        if full_path.is_dir():
            shutil.copytree(full_path, candidate)
        else:
            shutil.copy2(full_path, candidate)
        return str(candidate.relative_to(self._root))

    def move(self, source_path: str, dest_dir_path: str) -> str:
        """Move a file or folder into a destination directory."""
        source = self._resolve_safe(source_path)
        dest_dir = self._resolve_safe(dest_dir_path)
        if not source.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")
        if not dest_dir.is_dir():
            raise ValueError(f"Destination is not a directory: {dest_dir_path}")
        new_path = dest_dir / source.name
        if new_path.exists():
            raise ValueError(f"A file named '{source.name}' already exists in '{dest_dir_path}'.")
        shutil.move(str(source), str(new_path))
        return str(new_path.relative_to(self._root))

    def absolute_path(self, relative_path: str) -> str:
        """Return the absolute filesystem path for a workspace-relative path."""
        return str(self._resolve_safe(relative_path))

    def relative_path(self, absolute_path: str) -> str:
        """Return the workspace-relative path for an absolute filesystem path."""
        return str(Path(absolute_path).relative_to(self._root))

    def _resolve_safe(self, relative_path: str) -> Path:
        """Resolve path and guard against directory traversal attacks."""
        resolved = (self._root / relative_path).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise ValueError(f"Path '{relative_path}' escapes the workspace root.")
        return resolved

    def _build_tree(self, directory: Path, git_tracked_paths: set[str]) -> list[WorkspaceNode]:
        nodes: list[WorkspaceNode] = []
        for child in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name == ".git":
                continue
            rel = str(child.relative_to(self._root))
            if child.is_dir():
                is_git = (child / ".git").is_dir() or rel in git_tracked_paths
                git_branch: str | None = None
                if is_git:
                    git_branch = self._read_branch(child)
                nodes.append(
                    WorkspaceNode(
                        name=child.name,
                        path=rel,
                        is_dir=True,
                        children=self._build_tree(child, git_tracked_paths),
                        is_git_folder=is_git,
                        git_branch=git_branch,
                    )
                )
            elif child.suffix in self.ALLOWED_EXTENSIONS:
                nodes.append(WorkspaceNode(name=child.name, path=rel, is_dir=False))
        return nodes

    @staticmethod
    def _read_branch(directory: Path) -> str | None:
        """Read the active branch name from a .git/HEAD file without importing gitpython."""
        head_file = directory / ".git" / "HEAD"
        if not head_file.exists():
            return None
        content = head_file.read_text(encoding="utf-8").strip()
        if content.startswith("ref: refs/heads/"):
            return content[len("ref: refs/heads/") :]
        return content[:7] if len(content) >= 7 else content
