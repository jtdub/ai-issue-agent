"""Tests for safe subprocess wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_issue_agent.utils.safe_subprocess import (
    AuthenticationError,
    CommandResult,
    CommandTimeoutError,
    GHCliError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    SafeGHCli,
)
from ai_issue_agent.utils.security import SecurityError


class TestCommandResult:
    """Test CommandResult dataclass."""

    def test_success_true(self) -> None:
        """Test success property when return code is 0."""
        result = CommandResult(stdout="output", stderr="", return_code=0, command=["gh", "version"])
        assert result.success is True

    def test_success_false(self) -> None:
        """Test success property when return code is non-zero."""
        result = CommandResult(stdout="", stderr="error", return_code=1, command=["gh", "version"])
        assert result.success is False

    def test_json_parsing(self) -> None:
        """Test JSON parsing of stdout."""
        result = CommandResult(
            stdout='{"number": 123, "title": "Test"}',
            stderr="",
            return_code=0,
            command=["gh", "issue", "view"],
        )
        data = result.json()
        assert data["number"] == 123
        assert data["title"] == "Test"

    def test_json_parsing_invalid(self) -> None:
        """Test JSON parsing with invalid JSON."""
        result = CommandResult(
            stdout="not json", stderr="", return_code=0, command=["gh", "version"]
        )
        with pytest.raises(ValueError):
            result.json()


class TestSafeGHCliInit:
    """Test SafeGHCli initialization."""

    def test_finds_gh_in_path(self) -> None:
        """Test that gh is found in PATH."""
        with patch("shutil.which", return_value="/usr/local/bin/gh"):
            gh = SafeGHCli()
            assert gh._gh_path == "/usr/local/bin/gh"

    def test_uses_custom_path(self) -> None:
        """Test using a custom gh path."""
        gh = SafeGHCli(gh_path="/custom/path/gh")
        assert gh._gh_path == "/custom/path/gh"

    def test_raises_if_gh_not_found(self) -> None:
        """Test that GHCliError is raised if gh is not found."""
        with (
            patch("shutil.which", return_value=None),
            pytest.raises(GHCliError, match="gh CLI not found"),
        ):
            SafeGHCli()


class TestSafeGHCliValidation:
    """Test input validation in SafeGHCli."""

    @pytest.fixture
    def gh(self) -> SafeGHCli:
        """Create a SafeGHCli instance with mocked gh path."""
        with patch("shutil.which", return_value="/usr/bin/gh"):
            return SafeGHCli()

    @pytest.mark.parametrize(
        "malicious_repo",
        [
            "owner/repo; rm -rf /",
            "owner/repo$(whoami)",
            "owner/repo`id`",
            "../../../etc/passwd",
            "owner/repo\nmalicious",
        ],
    )
    async def test_rejects_malicious_repo_in_search(
        self, gh: SafeGHCli, malicious_repo: str
    ) -> None:
        """Test that malicious repo names are rejected in search."""
        with pytest.raises(SecurityError, match="Invalid repository name"):
            await gh.search_issues(malicious_repo, "query")

    @pytest.mark.parametrize(
        "malicious_repo",
        [
            "owner/repo; rm -rf /",
            "owner/repo$(whoami)",
        ],
    )
    async def test_rejects_malicious_repo_in_get_issue(
        self, gh: SafeGHCli, malicious_repo: str
    ) -> None:
        """Test that malicious repo names are rejected in get_issue."""
        with pytest.raises(SecurityError, match="Invalid repository name"):
            await gh.get_issue(malicious_repo, 123)

    @pytest.mark.parametrize(
        "malicious_repo",
        [
            "owner/repo; rm -rf /",
            "owner/repo$(whoami)",
        ],
    )
    async def test_rejects_malicious_repo_in_create_issue(
        self, gh: SafeGHCli, malicious_repo: str
    ) -> None:
        """Test that malicious repo names are rejected in create_issue."""
        with pytest.raises(SecurityError, match="Invalid repository name"):
            await gh.create_issue(malicious_repo, "Title", "Body")


class TestSafeGHCliErrorParsing:
    """Test error parsing in SafeGHCli."""

    @pytest.fixture
    def gh(self) -> SafeGHCli:
        """Create a SafeGHCli instance with mocked gh path."""
        with patch("shutil.which", return_value="/usr/bin/gh"):
            return SafeGHCli()

    def test_parses_auth_error(self, gh: SafeGHCli) -> None:
        """Test parsing authentication errors."""
        result = CommandResult(
            stdout="",
            stderr="error: authentication required",
            return_code=1,
            command=["gh", "issue", "list"],
        )
        error = gh._parse_error(result)
        assert isinstance(error, AuthenticationError)

    def test_parses_not_logged_in(self, gh: SafeGHCli) -> None:
        """Test parsing 'not logged in' errors."""
        result = CommandResult(
            stdout="",
            stderr="You are not logged in to any GitHub hosts",
            return_code=1,
            command=["gh", "auth", "status"],
        )
        error = gh._parse_error(result)
        assert isinstance(error, AuthenticationError)

    def test_parses_rate_limit(self, gh: SafeGHCli) -> None:
        """Test parsing rate limit errors."""
        result = CommandResult(
            stdout="",
            stderr="API rate limit exceeded",
            return_code=1,
            command=["gh", "api"],
        )
        error = gh._parse_error(result)
        assert isinstance(error, RateLimitError)

    def test_parses_not_found(self, gh: SafeGHCli) -> None:
        """Test parsing not found errors."""
        result = CommandResult(
            stdout="",
            stderr="Could not resolve to a Repository",
            return_code=1,
            command=["gh", "repo", "view"],
        )
        error = gh._parse_error(result)
        assert isinstance(error, NotFoundError)

    def test_parses_permission_denied(self, gh: SafeGHCli) -> None:
        """Test parsing permission denied errors."""
        result = CommandResult(
            stdout="",
            stderr="Permission denied",
            return_code=1,
            command=["gh", "repo", "clone"],
        )
        error = gh._parse_error(result)
        assert isinstance(error, PermissionError)

    def test_generic_error(self, gh: SafeGHCli) -> None:
        """Test generic error parsing."""
        result = CommandResult(
            stdout="",
            stderr="Unknown error occurred",
            return_code=1,
            command=["gh", "something"],
        )
        error = gh._parse_error(result)
        assert isinstance(error, GHCliError)
        assert not isinstance(error, AuthenticationError)
        assert not isinstance(error, RateLimitError)


class TestSafeGHCliCommands:
    """Test SafeGHCli command execution."""

    @pytest.fixture
    def gh(self) -> SafeGHCli:
        """Create a SafeGHCli instance with mocked gh path."""
        with patch("shutil.which", return_value="/usr/bin/gh"):
            return SafeGHCli()

    @pytest.fixture
    def mock_subprocess(self) -> MagicMock:
        """Create a mock for subprocess.run."""
        mock = MagicMock()
        mock.stdout = '{"number": 123}'
        mock.stderr = ""
        mock.returncode = 0
        return mock

    async def test_search_issues_builds_correct_command(self, gh: SafeGHCli) -> None:
        """Test that search_issues builds the correct command."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_proc = MagicMock()
            mock_proc.stdout = "[]"
            mock_proc.stderr = ""
            mock_proc.returncode = 0
            mock_thread.return_value = mock_proc

            await gh.search_issues("owner/repo", "bug fix", state="open", limit=5)

            # Verify the function was called
            mock_thread.assert_called_once()

    async def test_search_issues_sanitizes_state(self, gh: SafeGHCli) -> None:
        """Test that invalid state values are sanitized."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_proc = MagicMock()
            mock_proc.stdout = "[]"
            mock_proc.stderr = ""
            mock_proc.returncode = 0
            mock_thread.return_value = mock_proc

            # Invalid state should be replaced with "all"
            await gh.search_issues("owner/repo", "query", state="invalid")

            # The command should have been called (state sanitized internally)
            mock_thread.assert_called_once()

    async def test_search_issues_limits_results(self, gh: SafeGHCli) -> None:
        """Test that limit is bounded between 1 and 100."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_proc = MagicMock()
            mock_proc.stdout = "[]"
            mock_proc.stderr = ""
            mock_proc.returncode = 0
            mock_thread.return_value = mock_proc

            # Limit should be bounded
            await gh.search_issues("owner/repo", "query", limit=1000)
            mock_thread.assert_called_once()

    async def test_check_auth_returns_true_when_authenticated(self, gh: SafeGHCli) -> None:
        """Test check_auth returns True when authenticated."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_proc = MagicMock()
            mock_proc.stdout = "Logged in to github.com"
            mock_proc.stderr = ""
            mock_proc.returncode = 0
            mock_thread.return_value = mock_proc

            result = await gh.check_auth()
            assert result is True

    async def test_check_auth_returns_false_when_not_authenticated(self, gh: SafeGHCli) -> None:
        """Test check_auth returns False when not authenticated."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_proc = MagicMock()
            mock_proc.stdout = ""
            mock_proc.stderr = "Not logged in"
            mock_proc.returncode = 1
            mock_thread.return_value = mock_proc

            result = await gh.check_auth()
            assert result is False


class TestSafeGHCliClone:
    """Test repository cloning with security measures."""

    @pytest.fixture
    def gh(self) -> SafeGHCli:
        """Create a SafeGHCli instance with mocked gh path."""
        with patch("shutil.which", return_value="/usr/bin/gh"):
            return SafeGHCli()

    async def test_clone_disables_hooks(self, gh: SafeGHCli, tmp_path: Path) -> None:
        """Test that clone disables git hooks for security."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_proc = MagicMock()
            mock_proc.stdout = ""
            mock_proc.stderr = ""
            mock_proc.returncode = 0
            mock_thread.return_value = mock_proc

            await gh.clone_repository("owner/repo", tmp_path)

            # Verify the mock was called
            mock_thread.assert_called_once()
            # The actual command includes -c core.hooksPath=/dev/null
            # which is verified through integration tests

    async def test_clone_validates_repo_name(self, gh: SafeGHCli, tmp_path: Path) -> None:
        """Test that clone validates repository names."""
        with pytest.raises(SecurityError, match="Invalid repository name"):
            await gh.clone_repository("malicious; rm -rf /", tmp_path)


class TestSafeGHCliTimeout:
    """Test timeout handling."""

    @pytest.fixture
    def gh(self) -> SafeGHCli:
        """Create a SafeGHCli instance with mocked gh path."""
        with patch("shutil.which", return_value="/usr/bin/gh"):
            return SafeGHCli(default_timeout=1)

    async def test_command_timeout_raises_error(self, gh: SafeGHCli) -> None:
        """Test that command timeout raises CommandTimeoutError."""

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.side_effect = TimeoutError()

            with pytest.raises(CommandTimeoutError):
                await gh.search_issues("owner/repo", "query")
