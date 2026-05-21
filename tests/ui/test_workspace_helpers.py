"""Unit tests for workspace page helper utilities."""

from __future__ import annotations

from app.ui.workspace_utils import folder_name_from_url


class TestFolderNameFromUrl:
    def test_plain_github_url(self):
        assert folder_name_from_url("https://github.com/user/my-repo") == "my-repo"

    def test_url_with_git_suffix(self):
        assert folder_name_from_url("https://github.com/user/my-repo.git") == "my-repo"

    def test_url_with_trailing_slash(self):
        assert folder_name_from_url("https://github.com/user/my-repo/") == "my-repo"

    def test_url_with_credentials_embedded(self):
        assert (
            folder_name_from_url("https://token:x@github.com/user/pipeline_finance")
            == "pipeline_finance"
        )

    def test_ssh_style_url(self):
        assert folder_name_from_url("git@github.com:user/data-pipeline.git") == "data-pipeline"

    def test_strips_both_slash_and_git_suffix(self):
        assert folder_name_from_url("https://gitlab.com/org/repo.git/") == "repo"

    def test_short_name_only(self):
        assert folder_name_from_url("my-project") == "my-project"

    def test_whitespace_is_stripped(self):
        assert folder_name_from_url("  https://github.com/user/clean-repo  ") == "clean-repo"
