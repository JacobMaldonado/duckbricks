"""Abstract base for git provider implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Repository:
    """Lightweight representation of a remote repository."""

    name: str
    full_name: str
    clone_url: str
    default_branch: str
    description: str = ""


class GitProvider(ABC):
    """Contract that all git provider implementations must fulfill."""

    @abstractmethod
    def validate(self) -> bool:
        """Return True if the stored credentials are valid and not expired."""

    @abstractmethod
    def list_repositories(self) -> list[Repository]:
        """Return repositories accessible with the current credentials."""

    @abstractmethod
    def clone(self, repo_url: str, destination: str, branch: str) -> None:
        """Clone a repository into the given destination directory on the given branch."""

    @abstractmethod
    def provider_type(self) -> str:
        """Return the canonical provider type identifier (e.g. 'github')."""
