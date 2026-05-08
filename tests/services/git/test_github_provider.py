"""Tests for GitHubPatProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.git.providers.github import GitHubPatProvider


def _make_provider(token: str = "test-token") -> GitHubPatProvider:
    return GitHubPatProvider(token=token)


def test_provider_type_is_github():
    assert _make_provider().provider_type() == "github"


def test_validate_returns_true_on_200():
    provider = _make_provider()
    mock_response = MagicMock()
    mock_response.status_code = 200
    with patch.object(provider, "_authenticated_get", return_value=mock_response):
        assert provider.validate() is True


def test_validate_returns_false_on_401():
    provider = _make_provider()
    mock_response = MagicMock()
    mock_response.status_code = 401
    with patch.object(provider, "_authenticated_get", return_value=mock_response):
        assert provider.validate() is False


def test_validate_returns_false_on_exception():
    provider = _make_provider()
    with patch.object(provider, "_authenticated_get", side_effect=Exception("timeout")):
        assert provider.validate() is False


def test_list_repositories_parses_response():
    provider = _make_provider()
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "name": "my-repo",
            "full_name": "user/my-repo",
            "clone_url": "https://github.com/user/my-repo.git",
            "default_branch": "main",
            "description": "A test repo",
        }
    ]
    with patch.object(provider, "_authenticated_get", return_value=mock_response):
        repos = provider.list_repositories()
    assert len(repos) == 1
    assert repos[0].name == "my-repo"
    assert repos[0].full_name == "user/my-repo"
    assert repos[0].default_branch == "main"


def test_inject_token_replaces_https_prefix():
    provider = _make_provider(token="abc123")
    url = "https://github.com/user/repo.git"
    result = provider._inject_token_into_url(url)
    assert result == "https://oauth2:abc123@github.com/user/repo.git"


def test_inject_token_leaves_ssh_url_unchanged():
    provider = _make_provider(token="abc123")
    url = "git@github.com:user/repo.git"
    result = provider._inject_token_into_url(url)
    assert result == url
