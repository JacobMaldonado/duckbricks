"""Tests for GitProviderFactory."""

from __future__ import annotations

import pytest

from app.services.git.providers.factory import GitProviderFactory
from app.services.git.providers.github import GitHubPatProvider


def test_build_github_returns_github_provider():
    provider = GitProviderFactory.build("github", token="tok")
    assert isinstance(provider, GitHubPatProvider)


def test_build_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown provider type"):
        GitProviderFactory.build("bitbucket", token="tok")


def test_supported_types_includes_github():
    assert "github" in GitProviderFactory.supported_types()
