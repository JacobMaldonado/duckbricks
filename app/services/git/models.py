"""Shared data models for the git service layer."""

from __future__ import annotations

from dataclasses import dataclass, field


class GitAuthError(Exception):
    """Raised when a git remote operation fails due to authentication."""


@dataclass
class ChangedFile:
    """Represents a single file with outstanding changes in a git repository."""

    path: str
    status: str  # "modified" | "added" | "deleted" | "untracked" | "renamed"
    is_staged: bool

    @property
    def status_label(self) -> str:
        """Return a single-letter label suitable for display in the UI."""
        return {
            "modified": "M",
            "added": "A",
            "deleted": "D",
            "untracked": "U",
            "renamed": "R",
        }.get(self.status, "?")

    @property
    def status_color(self) -> str:
        """Return a Quasar colour name for the status badge."""
        return {
            "modified": "orange-8",
            "added": "green-8",
            "deleted": "red-8",
            "untracked": "blue-7",
            "renamed": "purple-7",
        }.get(self.status, "grey-6")


@dataclass
class GitStatus:
    """Aggregated status of a git repository."""

    branch: str
    changed_files: list[ChangedFile] = field(default_factory=list)
    has_upstream: bool = True
