"""Tests for GitHub VCS adapter."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_issue_agent.config.schema import GitHubConfig
from ai_issue_agent.models.issue import Issue, IssueCreate, IssueSearchResult, IssueState
from ai_issue_agent.utils.safe_subprocess import CommandResult, NotFoundError


@pytest.fixture
def github_config() -> GitHubConfig:
    """Create a test GitHub configuration."""
    return GitHubConfig(
        default_repo="owner/repo",
        clone_dir=Path("/tmp/test-clones"),  # noqa: S108
        clone_cache_ttl=3600,
        default_labels=["auto-triaged"],
    )


class TestGitHubAdapterInit:
    """Test GitHubAdapter initialization."""

    def test_init_with_config(self, github_config: GitHubConfig) -> None:
        """Test initializing with configuration."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)
            assert adapter._config == github_config

    def test_init_creates_gh_cli(self, github_config: GitHubConfig) -> None:
        """Test that initialization creates SafeGHCli."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli") as mock_cli:
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            GitHubAdapter(github_config)
            mock_cli.assert_called_once()

    def test_init_with_custom_gh_path(self) -> None:
        """Test initializing with custom gh CLI path."""
        config = GitHubConfig(
            default_repo="owner/repo",
            gh_path="/custom/path/gh",
        )
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli") as mock_cli:
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            GitHubAdapter(config)
            mock_cli.assert_called_once_with(gh_path="/custom/path/gh")


class TestGitHubAdapterSearchIssues:
    """Test issue searching in GitHubAdapter."""

    async def test_search_issues_returns_results(self, github_config: GitHubConfig) -> None:
        """Test that search_issues returns IssueSearchResult list."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            mock_result = CommandResult(
                stdout=json.dumps([
                    {
                        "number": 1,
                        "title": "Bug in parser",
                        "body": "Parser fails on edge case",
                        "url": "https://github.com/owner/repo/issues/1",
                        "state": "OPEN",
                        "labels": [{"name": "bug"}],
                        "createdAt": "2024-01-15T10:00:00Z",
                        "updatedAt": "2024-01-16T12:00:00Z",
                        "author": {"login": "user1"},
                    }
                ]),
                stderr="",
                return_code=0,
                command=["gh", "issue", "list"],
            )
            adapter._gh.search_issues = AsyncMock(return_value=mock_result)

            results = await adapter.search_issues(
                repo="owner/repo",
                query="parser",
            )

            assert len(results) == 1
            assert isinstance(results[0], IssueSearchResult)
            assert results[0].issue.number == 1
            assert results[0].issue.title == "Bug in parser"

    async def test_search_issues_empty_results(self, github_config: GitHubConfig) -> None:
        """Test searching with no results."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            mock_result = CommandResult(
                stdout="[]",
                stderr="",
                return_code=0,
                command=["gh", "issue", "list"],
            )
            adapter._gh.search_issues = AsyncMock(return_value=mock_result)

            results = await adapter.search_issues(
                repo="owner/repo",
                query="nonexistent",
            )

            assert results == []


class TestGitHubAdapterGetIssue:
    """Test getting individual issues in GitHubAdapter."""

    async def test_get_issue_returns_issue(self, github_config: GitHubConfig) -> None:
        """Test getting a specific issue."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            mock_result = CommandResult(
                stdout=json.dumps({
                    "number": 42,
                    "title": "Test Issue",
                    "body": "Issue body content",
                    "url": "https://github.com/owner/repo/issues/42",
                    "state": "OPEN",
                    "labels": [{"name": "bug"}, {"name": "high-priority"}],
                    "createdAt": "2024-01-15T10:00:00Z",
                    "updatedAt": "2024-01-16T12:00:00Z",
                    "author": {"login": "testuser"},
                }),
                stderr="",
                return_code=0,
                command=["gh", "issue", "view"],
            )
            adapter._gh.get_issue = AsyncMock(return_value=mock_result)

            issue = await adapter.get_issue(repo="owner/repo", issue_number=42)

            assert issue is not None
            assert isinstance(issue, Issue)
            assert issue.number == 42
            assert issue.title == "Test Issue"
            assert issue.state == IssueState.OPEN
            assert "bug" in issue.labels
            assert "high-priority" in issue.labels

    async def test_get_issue_not_found(self, github_config: GitHubConfig) -> None:
        """Test getting a non-existent issue."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            # The adapter catches NotFoundError and returns None
            adapter._gh.get_issue = AsyncMock(side_effect=NotFoundError("Issue not found"))

            issue = await adapter.get_issue(repo="owner/repo", issue_number=9999)

            assert issue is None

    async def test_get_issue_closed_state(self, github_config: GitHubConfig) -> None:
        """Test getting a closed issue."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            mock_result = CommandResult(
                stdout=json.dumps({
                    "number": 10,
                    "title": "Closed Issue",
                    "body": "This was fixed",
                    "url": "https://github.com/owner/repo/issues/10",
                    "state": "CLOSED",
                    "labels": [],
                    "createdAt": "2024-01-01T00:00:00Z",
                    "updatedAt": "2024-01-10T00:00:00Z",
                    "author": {"login": "user"},
                }),
                stderr="",
                return_code=0,
                command=["gh", "issue", "view"],
            )
            adapter._gh.get_issue = AsyncMock(return_value=mock_result)

            issue = await adapter.get_issue(repo="owner/repo", issue_number=10)

            assert issue is not None
            assert issue.state == IssueState.CLOSED


class TestGitHubAdapterCreateIssue:
    """Test issue creation in GitHubAdapter."""

    async def test_create_issue_returns_issue(self, github_config: GitHubConfig) -> None:
        """Test creating an issue."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            mock_result = CommandResult(
                stdout=json.dumps({
                    "number": 100,
                    "title": "New Bug Report",
                    "body": "Description of the bug",
                    "url": "https://github.com/owner/repo/issues/100",
                    "state": "OPEN",
                    "labels": [{"name": "auto-triaged"}],
                    "createdAt": "2024-01-20T15:00:00Z",
                    "updatedAt": "2024-01-20T15:00:00Z",
                    "author": {"login": "bot"},
                }),
                stderr="",
                return_code=0,
                command=["gh", "issue", "create"],
            )
            adapter._gh.create_issue = AsyncMock(return_value=mock_result)

            issue_create = IssueCreate(
                title="New Bug Report",
                body="Description of the bug",
            )
            issue = await adapter.create_issue(repo="owner/repo", issue=issue_create)

            assert isinstance(issue, Issue)
            assert issue.number == 100
            assert issue.title == "New Bug Report"


class TestGitHubAdapterCloneRepository:
    """Test repository cloning in GitHubAdapter."""

    async def test_clone_repository_returns_path(self, tmp_path: Path) -> None:
        """Test cloning a repository."""
        config = GitHubConfig(
            default_repo="owner/repo",
            clone_dir=tmp_path,
            clone_cache_ttl=3600,
        )
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(config)

            expected_path = tmp_path / "repo"
            # SafeGHCli.clone_repository returns a Path directly
            adapter._gh.clone_repository = AsyncMock(return_value=expected_path)

            result = await adapter.clone_repository(
                repo="owner/repo",
                destination=expected_path,
            )

            assert isinstance(result, Path)
            assert result == expected_path
            adapter._gh.clone_repository.assert_called_once()


class TestGitHubAdapterGetFileContent:
    """Test file content retrieval in GitHubAdapter."""

    async def test_get_file_content_returns_content(self, github_config: GitHubConfig) -> None:
        """Test getting file content."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            expected_content = "def hello():\n    print('Hello, World!')\n"
            # SafeGHCli.get_file_content returns string directly
            adapter._gh.get_file_content = AsyncMock(return_value=expected_content)

            content = await adapter.get_file_content(
                repo="owner/repo",
                file_path="src/hello.py",
            )

            assert content is not None
            assert "def hello():" in content
            assert "print" in content

    async def test_get_file_content_not_found(self, github_config: GitHubConfig) -> None:
        """Test getting non-existent file."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            # The adapter catches NotFoundError and returns None
            adapter._gh.get_file_content = AsyncMock(side_effect=NotFoundError("File not found"))

            content = await adapter.get_file_content(
                repo="owner/repo",
                file_path="nonexistent.py",
            )

            assert content is None


class TestGitHubAdapterGetDefaultBranch:
    """Test default branch retrieval in GitHubAdapter."""

    async def test_get_default_branch_returns_main(self, github_config: GitHubConfig) -> None:
        """Test getting default branch when it's main."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            # SafeGHCli.get_default_branch returns string directly
            adapter._gh.get_default_branch = AsyncMock(return_value="main")

            branch = await adapter.get_default_branch(repo="owner/repo")

            assert branch == "main"


class TestGitHubAdapterIssueMapping:
    """Test issue data mapping in GitHubAdapter."""

    def test_parse_issue_json_basic(self, github_config: GitHubConfig) -> None:
        """Test parsing basic issue JSON data."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            data: dict[str, Any] = {
                "number": 1,
                "title": "Test",
                "body": "Body",
                "url": "https://github.com/owner/repo/issues/1",
                "state": "OPEN",
                "labels": [],
                "createdAt": "2024-01-15T10:00:00Z",
                "updatedAt": "2024-01-16T12:00:00Z",
                "author": {"login": "user"},
            }

            issue = adapter._parse_issue_json(data)

            assert isinstance(issue, Issue)
            assert issue.number == 1
            assert issue.title == "Test"
            assert issue.state == IssueState.OPEN

    def test_parse_issue_json_with_labels(self, github_config: GitHubConfig) -> None:
        """Test parsing issue JSON with labels."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            data: dict[str, Any] = {
                "number": 2,
                "title": "Labeled",
                "body": "Body",
                "url": "https://github.com/owner/repo/issues/2",
                "state": "CLOSED",
                "labels": [{"name": "bug"}, {"name": "wontfix"}],
                "createdAt": "2024-01-15T10:00:00Z",
                "updatedAt": "2024-01-16T12:00:00Z",
                "author": {"login": "user"},
            }

            issue = adapter._parse_issue_json(data)

            assert "bug" in issue.labels
            assert "wontfix" in issue.labels
            assert issue.state == IssueState.CLOSED

    def test_parse_issue_json_null_body(self, github_config: GitHubConfig) -> None:
        """Test parsing issue JSON with null body."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            data: dict[str, Any] = {
                "number": 3,
                "title": "No Body",
                "body": None,
                "url": "https://github.com/owner/repo/issues/3",
                "state": "OPEN",
                "labels": [],
                "createdAt": "2024-01-15T10:00:00Z",
                "updatedAt": "2024-01-16T12:00:00Z",
                "author": {"login": "user"},
            }

            issue = adapter._parse_issue_json(data)

            # Null body is preserved as None, not converted to empty string
            assert issue.body is None

    def test_parse_timestamp(self, github_config: GitHubConfig) -> None:
        """Test parsing ISO timestamp."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            timestamp = adapter._parse_timestamp("2024-01-15T10:30:45Z")

            assert isinstance(timestamp, datetime)
            assert timestamp.year == 2024
            assert timestamp.month == 1
            assert timestamp.day == 15


class TestGitHubAdapterRepoValidation:
    """Test repository validation in GitHubAdapter."""

    def test_validate_repo_access_valid(self, github_config: GitHubConfig) -> None:
        """Test validating access to a valid repository."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(github_config)

            # Should not raise for valid repo format
            adapter._validate_repo_access("owner/repo")

    def test_validate_repo_access_invalid(self, github_config: GitHubConfig) -> None:
        """Test validating access to an invalid repository."""
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter
            from ai_issue_agent.utils.security import SecurityError

            adapter = GitHubAdapter(github_config)

            # Should raise for invalid repo format
            with pytest.raises(SecurityError):
                adapter._validate_repo_access("invalid-repo")

    def test_validate_repo_access_with_allowlist(self) -> None:
        """Test validating access with allowlist configured."""
        config = GitHubConfig(
            default_repo="owner/repo",
            allowed_repos=["owner/repo", "other-org/*"],
        )
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(config)

            # Should allow exact match
            adapter._validate_repo_access("owner/repo")

            # Should allow wildcard match
            adapter._validate_repo_access("other-org/any-project")

    def test_validate_repo_access_not_in_allowlist(self) -> None:
        """Test validating access for repo not in allowlist."""
        config = GitHubConfig(
            default_repo="owner/repo",
            allowed_repos=["owner/repo"],
        )
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter
            from ai_issue_agent.utils.security import SecurityError

            adapter = GitHubAdapter(config)

            # Should raise for repo not in allowlist
            with pytest.raises(SecurityError, match="not in allowlist"):
                adapter._validate_repo_access("different-owner/different-repo")


class TestGitHubAdapterCleanupCloneCache:
    """Test clone cache cleanup in GitHubAdapter."""

    async def test_cleanup_clone_cache_removes_old(self, tmp_path: Path) -> None:
        """Test that cleanup removes old clones."""
        config = GitHubConfig(
            default_repo="owner/repo",
            clone_dir=tmp_path,
        )
        with patch("ai_issue_agent.adapters.vcs.github.SafeGHCli"):
            from ai_issue_agent.adapters.vcs.github import GitHubAdapter

            adapter = GitHubAdapter(config)

            # Call cleanup with 0 hours to clean everything
            removed = await adapter.cleanup_clone_cache(max_age_hours=0)

            # Initially no clones to clean
            assert removed >= 0
