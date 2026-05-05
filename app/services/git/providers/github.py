"""GitHub Personal Access Token (PAT) provider implementation."""

from __future__ import annotations

import logging

import git
import httpx

from app.services.git.providers.base import GitProvider, Repository

_log = logging.getLogger(__name__)

_GITHUB_API_URL = "https://api.github.com"


class GitHubPatProvider(GitProvider):
    """Authenticates with GitHub using a Personal Access Token."""

    def __init__(self, token: str, host: str | None = None) -> None:
        self._token = token
        self._host = host or _GITHUB_API_URL

    def provider_type(self) -> str:
        return "github"

    def validate(self) -> bool:
        """Return True if the PAT resolves to a valid GitHub user."""
        try:
            response = self._authenticated_get("/user")
            result: bool = response.status_code == 200
            return result
        except Exception as exc:
            _log.warning("GitHub PAT validation failed: %s", exc)
            return False

    def list_repositories(self) -> list[Repository]:
        """Return all repositories accessible to the authenticated user."""
        response = self._authenticated_get("/user/repos?per_page=100&sort=updated")
        response.raise_for_status()
        return [self._parse_repository(item) for item in response.json()]

    def clone(self, repo_url: str, destination: str, branch: str) -> None:
        """Clone the repository using the PAT embedded in the URL for authentication."""
        authenticated_url = self._inject_token_into_url(repo_url)
        git.Repo.clone_from(authenticated_url, destination, branch=branch)

    def _authenticated_get(self, path: str) -> httpx.Response:
        with httpx.Client(base_url=self._host) as client:
            return client.get(
                path,
                headers={
                    "Authorization": f"token {self._token}",
                    "Accept": "application/vnd.github+json",
                },
            )

    def _inject_token_into_url(self, url: str) -> str:
        """Embed the PAT into an HTTPS clone URL for authentication during clone."""
        if url.startswith("https://"):
            return url.replace("https://", f"https://oauth2:{self._token}@", 1)
        return url

    @staticmethod
    def _parse_repository(data: dict) -> Repository:
        return Repository(
            name=data["name"],
            full_name=data["full_name"],
            clone_url=data["clone_url"],
            default_branch=data.get("default_branch", "main"),
            description=data.get("description") or "",
        )
