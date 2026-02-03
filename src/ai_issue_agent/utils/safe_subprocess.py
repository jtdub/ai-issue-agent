"""Safe subprocess wrapper for gh CLI operations.

This module provides a secure wrapper around the GitHub CLI (gh) that:
- Never uses shell=True
- Validates all inputs before execution
- Enforces timeouts on all operations
- Parses and handles common error conditions

See docs/SECURITY.md for security guidelines.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

from ai_issue_agent.utils.security import SecurityError, validate_repo_name

log = structlog.get_logger()


class GHCliError(SecurityError):
    """Base exception for gh CLI errors."""


class AuthenticationError(GHCliError):
    """Raised when gh CLI authentication fails."""


class RateLimitError(GHCliError):
    """Raised when GitHub rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class NotFoundError(GHCliError):
    """Raised when a resource is not found."""


class PermissionError(GHCliError):
    """Raised when permission is denied."""


class CommandTimeoutError(GHCliError):
    """Raised when a command times out."""


class GHOutputFormat(Enum):
    """Output format for gh CLI commands."""

    JSON = "json"
    TEXT = "text"


@dataclass
class CommandResult:
    """Result of a gh CLI command execution."""

    stdout: str
    stderr: str
    return_code: int
    command: list[str]

    @property
    def success(self) -> bool:
        """Return True if the command succeeded."""
        return self.return_code == 0

    def json(self) -> Any:
        """Parse stdout as JSON.

        Raises:
            ValueError: If stdout is not valid JSON.
        """
        return json.loads(self.stdout)


class SafeGHCli:
    """Safe wrapper for GitHub CLI (gh) operations.

    This class provides a secure interface to the gh CLI that:
    - Validates all repository names before use
    - Uses list-based subprocess calls (never shell=True)
    - Enforces timeouts on all operations
    - Parses common error conditions into specific exceptions

    Example:
        gh = SafeGHCli()
        result = await gh.search_issues("owner/repo", "bug in auth")
        issues = result.json()
    """

    # Default timeout for commands (seconds)
    DEFAULT_TIMEOUT = 30

    # Timeout for clone operations (seconds)
    CLONE_TIMEOUT = 120

    def __init__(
        self,
        gh_path: str | None = None,
        default_timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the SafeGHCli wrapper.

        Args:
            gh_path: Path to the gh CLI binary. If None, uses PATH.
            default_timeout: Default timeout for commands in seconds.

        Raises:
            GHCliError: If gh CLI is not found.
        """
        resolved_path = gh_path or self._find_gh()
        if not resolved_path:
            raise GHCliError("gh CLI not found. Please install it from https://cli.github.com")

        self._gh_path: str = resolved_path
        self._default_timeout = default_timeout

    def _find_gh(self) -> str | None:
        """Find the gh CLI binary in PATH."""
        return shutil.which("gh")

    def _validate_repo(self, repo: str) -> None:
        """Validate a repository name.

        Args:
            repo: Repository name in owner/repo format.

        Raises:
            SecurityError: If the repository name is invalid.
        """
        if not validate_repo_name(repo):
            msg = f"Invalid repository name: {repo}"
            log.warning("invalid_repo_name_rejected", repo=repo)
            raise SecurityError(msg)

    def _parse_error(self, result: CommandResult) -> GHCliError:
        """Parse a command result into a specific error type.

        Args:
            result: The failed command result.

        Returns:
            An appropriate exception for the error type.
        """
        stderr_lower = result.stderr.lower()
        stdout_lower = result.stdout.lower()
        combined = stderr_lower + stdout_lower

        # Check for authentication errors
        if "authentication" in combined or "not logged in" in combined:
            return AuthenticationError(f"Authentication failed: {result.stderr or result.stdout}")

        # Check for rate limiting
        if "rate limit" in combined or "api rate limit" in combined:
            return RateLimitError(f"Rate limit exceeded: {result.stderr or result.stdout}")

        # Check for not found
        if "not found" in combined or "could not resolve" in combined:
            return NotFoundError(f"Resource not found: {result.stderr or result.stdout}")

        # Check for permission errors
        if "permission denied" in combined or "forbidden" in combined:
            return PermissionError(f"Permission denied: {result.stderr or result.stdout}")

        # Generic error
        return GHCliError(f"Command failed: {result.stderr or result.stdout}")

    async def _run_command(
        self,
        args: list[str],
        timeout: int | None = None,
        check: bool = True,
    ) -> CommandResult:
        """Run a gh CLI command safely.

        Args:
            args: Command arguments (without 'gh' prefix).
            timeout: Timeout in seconds (uses default if None).
            check: If True, raise an exception on failure.

        Returns:
            CommandResult with stdout, stderr, and return code.

        Raises:
            CommandTimeoutError: If the command times out.
            GHCliError: If check=True and the command fails.
        """
        cmd = [self._gh_path, *args]
        effective_timeout = timeout or self._default_timeout

        log.debug("executing_gh_command", command=cmd, timeout=effective_timeout)

        try:
            # Use asyncio.to_thread to run subprocess in a thread pool
            def run_sync() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=effective_timeout,
                    shell=False,  # CRITICAL: Never use shell=True
                )

            proc = await asyncio.wait_for(
                asyncio.to_thread(run_sync),
                timeout=effective_timeout + 5,  # Extra buffer for thread overhead
            )

            result = CommandResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
                command=cmd,
            )

            if check and not result.success:
                raise self._parse_error(result)

            return result

        except subprocess.TimeoutExpired as e:
            msg = f"Command timed out after {effective_timeout}s: {cmd}"
            log.error("command_timeout", command=cmd, timeout=effective_timeout)
            raise CommandTimeoutError(msg) from e

        except TimeoutError as e:
            msg = f"Command timed out after {effective_timeout}s: {cmd}"
            log.error("command_timeout", command=cmd, timeout=effective_timeout)
            raise CommandTimeoutError(msg) from e

    async def check_auth(self) -> bool:
        """Check if gh CLI is authenticated.

        Returns:
            True if authenticated, False otherwise.
        """
        try:
            result = await self._run_command(["auth", "status"], check=False)
            return result.success
        except GHCliError:
            return False

    async def search_issues(
        self,
        repo: str,
        query: str,
        state: str = "all",
        limit: int = 10,
    ) -> CommandResult:
        """Search for issues in a repository.

        Args:
            repo: Repository in owner/repo format.
            query: Search query string.
            state: Issue state filter (open, closed, all).
            limit: Maximum number of results.

        Returns:
            CommandResult with JSON output.

        Raises:
            SecurityError: If repo name is invalid.
            GHCliError: If the command fails.
        """
        self._validate_repo(repo)

        # Sanitize state parameter
        if state not in ("open", "closed", "all"):
            state = "all"

        # Limit the limit parameter
        limit = min(max(1, limit), 100)

        args = [
            "issue",
            "list",
            "--repo",
            repo,
            "--search",
            query,
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            "number,title,body,state,labels,createdAt,updatedAt,author,url",
        ]

        return await self._run_command(args)

    async def get_issue(self, repo: str, number: int) -> CommandResult:
        """Get a specific issue by number.

        Args:
            repo: Repository in owner/repo format.
            number: Issue number.

        Returns:
            CommandResult with JSON output.

        Raises:
            SecurityError: If repo name is invalid.
            GHCliError: If the command fails.
        """
        self._validate_repo(repo)

        args = [
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,body,state,labels,createdAt,updatedAt,author,url",
        ]

        return await self._run_command(args)

    async def create_issue(
        self,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> CommandResult:
        """Create a new issue.

        Args:
            repo: Repository in owner/repo format.
            title: Issue title.
            body: Issue body (markdown).
            labels: List of label names to apply.

        Returns:
            CommandResult with JSON output.

        Raises:
            SecurityError: If repo name is invalid.
            GHCliError: If the command fails.
        """
        self._validate_repo(repo)

        args = [
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body",
            body,
            "--json",
            "number,title,url",
        ]

        if labels:
            for label in labels:
                args.extend(["--label", label])

        return await self._run_command(args)

    async def clone_repository(
        self,
        repo: str,
        destination: Path,
        branch: str | None = None,
        shallow: bool = True,
    ) -> Path:
        """Clone a repository safely.

        This method:
        - Validates the repository name
        - Disables git hooks (prevents malicious hook execution)
        - Uses shallow clone by default
        - Enforces a longer timeout for clone operations

        Args:
            repo: Repository in owner/repo format.
            destination: Directory to clone into.
            branch: Specific branch to clone (optional).
            shallow: If True, perform shallow clone (--depth 1).

        Returns:
            Path to the cloned repository.

        Raises:
            SecurityError: If repo name is invalid.
            GHCliError: If the clone fails.
        """
        self._validate_repo(repo)

        # The repo directory will be created inside destination
        repo_name = repo.split("/")[-1]
        repo_path = destination / repo_name

        args = [
            "repo",
            "clone",
            repo,
            str(repo_path),
            "--",
            "-c",
            "core.hooksPath=/dev/null",  # CRITICAL: Disable git hooks
        ]

        if shallow:
            args.extend(["--depth", "1"])

        if branch:
            args.extend(["--branch", branch])

        await self._run_command(args, timeout=self.CLONE_TIMEOUT)

        return repo_path

    async def get_file_content(
        self,
        repo: str,
        file_path: str,
        ref: str | None = None,
    ) -> str | None:
        """Get the content of a file from a repository.

        Args:
            repo: Repository in owner/repo format.
            file_path: Path to the file within the repository.
            ref: Git reference (branch, tag, commit). Uses default branch if None.

        Returns:
            File content as string, or None if file doesn't exist.

        Raises:
            SecurityError: If repo name is invalid.
            GHCliError: If the command fails (except for not found).
        """
        self._validate_repo(repo)

        # Build the API path
        api_path = f"/repos/{repo}/contents/{file_path}"
        if ref:
            api_path += f"?ref={ref}"

        args = ["api", api_path, "--jq", ".content"]

        try:
            result = await self._run_command(args)
            # Content is base64 encoded
            import base64

            content_b64 = result.stdout.strip().strip('"')
            if content_b64:
                return base64.b64decode(content_b64).decode("utf-8")
            return None
        except NotFoundError:
            return None

    async def get_default_branch(self, repo: str) -> str:
        """Get the default branch name for a repository.

        Args:
            repo: Repository in owner/repo format.

        Returns:
            The default branch name (e.g., "main", "master").

        Raises:
            SecurityError: If repo name is invalid.
            GHCliError: If the command fails.
        """
        self._validate_repo(repo)

        args = [
            "repo",
            "view",
            repo,
            "--json",
            "defaultBranchRef",
            "--jq",
            ".defaultBranchRef.name",
        ]

        result = await self._run_command(args)
        return result.stdout.strip()
