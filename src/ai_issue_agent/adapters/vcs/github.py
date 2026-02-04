"""GitHub VCS adapter using the gh CLI.

This module implements the VCSProvider protocol for GitHub using the
SafeGHCli wrapper, which ensures secure subprocess execution.

Security features:
- All repository names validated before use
- Git hooks disabled on clone operations
- Secret redaction applied to issue bodies before creation
- Timeout enforcement on all operations

See docs/SECURITY.md for security guidelines.
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from cachetools import TTLCache

from ...config.schema import GitHubConfig
from ...models.issue import Issue, IssueCreate, IssueSearchResult, IssueState
from ...utils.safe_subprocess import (
    AuthenticationError,
    CommandTimeoutError,
    GHCliError,
    NotFoundError,
    RateLimitError,
    SafeGHCli,
)
from ...utils.security import SecretRedactor, SecurityError, validate_repo_name

if TYPE_CHECKING:
    from typing import Any

log = structlog.get_logger()


class GitHubAdapterError(Exception):
    """Base exception for GitHub adapter errors."""


class CloneError(GitHubAdapterError):
    """Raised when repository cloning fails."""


class CreateError(GitHubAdapterError):
    """Raised when issue creation fails."""


class SearchError(GitHubAdapterError):
    """Raised when issue search fails."""


class GitHubAdapter:
    """GitHub VCS adapter implementing the VCSProvider protocol.

    This adapter uses the gh CLI through the SafeGHCli wrapper for all
    GitHub operations, ensuring secure execution and proper error handling.

    Example:
        config = GitHubConfig(default_repo="owner/repo")
        adapter = GitHubAdapter(config)

        # Search for issues
        results = await adapter.search_issues("owner/repo", "bug in auth")

        # Create an issue with automatic secret redaction
        issue = await adapter.create_issue("owner/repo", IssueCreate(
            title="Bug: Authentication fails",
            body="Details about the bug...",
        ))
    """

    def __init__(
        self,
        config: GitHubConfig,
        redactor: SecretRedactor | None = None,
    ) -> None:
        """Initialize the GitHub adapter.

        Args:
            config: GitHub-specific configuration.
            redactor: Secret redactor for issue bodies. If None, creates default.
        """
        self._config = config
        self._redactor = redactor or SecretRedactor()
        self._gh = SafeGHCli(gh_path=config.gh_path)

        # Clone cache: maps repo -> (path, timestamp)
        self._clone_cache: TTLCache[str, Path] = TTLCache(
            maxsize=100,
            ttl=config.clone_cache_ttl,
        )

        # Lock for concurrent clone operations
        self._clone_lock = asyncio.Lock()

    def _validate_repo_access(self, repo: str) -> None:
        """Validate that the repo is accessible according to config.

        Args:
            repo: Repository name in owner/repo format.

        Raises:
            SecurityError: If repo access is not allowed.
        """
        if not validate_repo_name(repo):
            raise SecurityError(f"Invalid repository name: {repo}")

        # Check allowlist if configured
        if self._config.allowed_repos:
            allowed = False
            for pattern in self._config.allowed_repos:
                if pattern == repo:
                    allowed = True
                    break
                if pattern.endswith("/*"):
                    org = pattern[:-2]
                    if repo.startswith(f"{org}/"):
                        allowed = True
                        break
            if not allowed:
                raise SecurityError(f"Repository {repo} not in allowlist")

    def _parse_issue_json(self, data: dict[str, Any]) -> Issue:
        """Parse issue JSON from gh CLI into Issue model.

        Args:
            data: JSON data from gh CLI.

        Returns:
            Issue model instance.
        """
        # Parse state
        state_str = data.get("state", "open").lower()
        state = IssueState.CLOSED if state_str == "closed" else IssueState.OPEN

        # Parse labels
        labels_data = data.get("labels", [])
        if isinstance(labels_data, list):
            labels = tuple(
                label.get("name", "") if isinstance(label, dict) else str(label)
                for label in labels_data
            )
        else:
            labels = ()

        # Parse timestamps
        created_at = self._parse_timestamp(data.get("createdAt", ""))
        updated_at = self._parse_timestamp(data.get("updatedAt", ""))

        # Parse author
        author_data = data.get("author", {})
        author = (
            author_data.get("login", "unknown")
            if isinstance(author_data, dict)
            else str(author_data)
        )

        return Issue(
            number=data.get("number", 0),
            title=data.get("title", ""),
            body=data.get("body", ""),
            url=data.get("url", ""),
            state=state,
            labels=labels,
            created_at=created_at,
            updated_at=updated_at,
            author=author,
        )

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse ISO timestamp from GitHub API.

        Args:
            timestamp_str: ISO format timestamp string.

        Returns:
            datetime object.
        """
        if not timestamp_str:
            return datetime.now()

        try:
            # GitHub uses ISO 8601 format with Z suffix
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            return datetime.now()

    async def search_issues(
        self,
        repo: str,
        query: str,
        state: str = "all",
        max_results: int = 10,
    ) -> list[IssueSearchResult]:
        """Search for issues matching the query.

        Args:
            repo: Repository identifier (e.g., "owner/repo").
            query: Search query string.
            state: Filter by issue state: "open", "closed", or "all".
            max_results: Maximum number of results to return.

        Returns:
            List of matching issues with relevance scores.

        Raises:
            SearchError: If search fails.
            SecurityError: If repo validation fails.
            RateLimitError: If rate limit exceeded.
        """
        self._validate_repo_access(repo)

        try:
            result = await self._gh.search_issues(
                repo=repo,
                query=query,
                state=state,
                limit=max_results,
            )

            issues_data = result.json()
            if not isinstance(issues_data, list):
                issues_data = []

            search_results: list[IssueSearchResult] = []
            for i, issue_data in enumerate(issues_data):
                issue = self._parse_issue_json(issue_data)
                # Calculate relevance score (simple position-based for now)
                # gh CLI doesn't provide relevance scores, so we use position
                relevance = 1.0 - (i * 0.1) if i < 10 else 0.1
                search_results.append(
                    IssueSearchResult(
                        issue=issue,
                        relevance_score=max(0.0, relevance),
                        matched_terms=tuple(query.split()[:5]),
                    )
                )

            log.info(
                "search_issues_complete",
                repo=repo,
                query=query,
                results_count=len(search_results),
            )
            return search_results

        except RateLimitError:
            log.warning("rate_limit_hit", repo=repo, operation="search_issues")
            raise
        except AuthenticationError as e:
            log.error("auth_error", repo=repo, error=str(e))
            raise SearchError(f"Authentication failed: {e}") from e
        except GHCliError as e:
            log.error("search_error", repo=repo, error=str(e))
            raise SearchError(f"Search failed: {e}") from e

    async def get_issue(
        self,
        repo: str,
        issue_number: int,
    ) -> Issue | None:
        """Fetch a specific issue by number.

        Args:
            repo: Repository identifier (e.g., "owner/repo").
            issue_number: Issue number.

        Returns:
            Issue if found, None otherwise.

        Raises:
            SecurityError: If repo validation fails.
            AuthenticationError: If not authorized.
        """
        self._validate_repo_access(repo)

        try:
            result = await self._gh.get_issue(repo=repo, number=issue_number)
            issue_data = result.json()
            return self._parse_issue_json(issue_data)

        except NotFoundError:
            log.debug("issue_not_found", repo=repo, issue_number=issue_number)
            return None
        except GHCliError as e:
            log.error("get_issue_error", repo=repo, issue_number=issue_number, error=str(e))
            raise

    async def create_issue(
        self,
        repo: str,
        issue: IssueCreate,
    ) -> Issue:
        """Create a new issue in the repository.

        Security: The issue body is automatically redacted to remove secrets
        before being sent to GitHub.

        Args:
            repo: Repository identifier (e.g., "owner/repo").
            issue: Issue creation data (title, body, labels, assignees).

        Returns:
            The created issue with assigned number and URL.

        Raises:
            CreateError: If issue creation fails.
            SecurityError: If repo validation fails or redaction fails.
        """
        self._validate_repo_access(repo)

        # CRITICAL: Redact secrets from issue body before sending to GitHub
        try:
            redacted_body = self._redactor.redact(issue.body)
            redacted_title = self._redactor.redact(issue.title)
        except Exception as e:
            log.error("redaction_failed", error=str(e))
            raise SecurityError(f"Failed to redact secrets from issue: {e}") from e

        # Combine default labels with issue-specific labels
        all_labels = list(self._config.default_labels) + list(issue.labels)

        try:
            result = await self._gh.create_issue(
                repo=repo,
                title=redacted_title,
                body=redacted_body,
                labels=all_labels if all_labels else None,
            )

            response_data = result.json()

            log.info(
                "issue_created",
                repo=repo,
                number=response_data.get("number"),
                url=response_data.get("url"),
            )

            # Return full issue object
            # The create response may not have all fields, so construct what we can
            return Issue(
                number=response_data.get("number", 0),
                title=redacted_title,
                body=redacted_body,
                url=response_data.get("url", ""),
                state=IssueState.OPEN,
                labels=tuple(all_labels),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                author="",  # Will be the authenticated user
            )

        except RateLimitError:
            log.warning("rate_limit_hit", repo=repo, operation="create_issue")
            raise
        except AuthenticationError as e:
            log.error("auth_error", repo=repo, error=str(e))
            raise CreateError(f"Authentication failed: {e}") from e
        except GHCliError as e:
            log.error("create_issue_error", repo=repo, error=str(e))
            raise CreateError(f"Failed to create issue: {e}") from e

    async def clone_repository(
        self,
        repo: str,
        destination: Path,
        branch: str | None = None,
        shallow: bool = True,
    ) -> Path:
        """Clone a repository to a local directory.

        Security: This method disables git hooks and uses secure clone options.

        Args:
            repo: Repository identifier (e.g., "owner/repo").
            destination: Local directory path.
            branch: Specific branch to clone (default: default branch).
            shallow: If True, perform shallow clone (--depth 1).

        Returns:
            Path to the cloned repository.

        Raises:
            CloneError: If cloning fails.
            SecurityError: If repo validation fails.
        """
        self._validate_repo_access(repo)

        # Check cache first
        cache_key = f"{repo}:{branch or 'default'}"
        if cache_key in self._clone_cache:
            cached_path = self._clone_cache[cache_key]
            if cached_path.exists():
                log.debug("clone_cache_hit", repo=repo, path=str(cached_path))
                return cached_path

        # Ensure destination exists
        destination.mkdir(parents=True, exist_ok=True)

        async with self._clone_lock:
            # Check cache again after acquiring lock
            if cache_key in self._clone_cache:
                cached_path = self._clone_cache[cache_key]
                if cached_path.exists():
                    return cached_path

            try:
                repo_path = await self._gh.clone_repository(
                    repo=repo,
                    destination=destination,
                    branch=branch,
                    shallow=shallow,
                )

                # Cache the result
                self._clone_cache[cache_key] = repo_path

                log.info(
                    "repository_cloned",
                    repo=repo,
                    path=str(repo_path),
                    branch=branch,
                    shallow=shallow,
                )

                return repo_path

            except CommandTimeoutError as e:
                log.error("clone_timeout", repo=repo, error=str(e))
                raise CloneError(f"Clone timed out: {e}") from e
            except AuthenticationError as e:
                log.error("auth_error", repo=repo, error=str(e))
                raise CloneError(f"Authentication failed: {e}") from e
            except GHCliError as e:
                log.error("clone_error", repo=repo, error=str(e))
                raise CloneError(f"Clone failed: {e}") from e

    async def get_file_content(
        self,
        repo: str,
        file_path: str,
        ref: str | None = None,
    ) -> str | None:
        """Fetch content of a file from the repository.

        Useful for reading files without full clone.

        Args:
            repo: Repository identifier (e.g., "owner/repo").
            file_path: Path to file within repository.
            ref: Git reference (branch, tag, commit). Uses default branch if None.

        Returns:
            File contents as string, None if file doesn't exist.

        Raises:
            SecurityError: If repo validation fails.
        """
        self._validate_repo_access(repo)

        try:
            content = await self._gh.get_file_content(
                repo=repo,
                file_path=file_path,
                ref=ref,
            )
            return content
        except NotFoundError:
            return None
        except GHCliError as e:
            log.error(
                "get_file_content_error",
                repo=repo,
                file_path=file_path,
                error=str(e),
            )
            raise

    async def get_default_branch(self, repo: str) -> str:
        """Get the default branch name for a repository.

        Args:
            repo: Repository identifier (e.g., "owner/repo").

        Returns:
            Default branch name (e.g., "main", "master").

        Raises:
            SecurityError: If repo validation fails.
            GHCliError: If the operation fails.
        """
        self._validate_repo_access(repo)

        try:
            return await self._gh.get_default_branch(repo)
        except GHCliError as e:
            log.error("get_default_branch_error", repo=repo, error=str(e))
            raise

    async def cleanup_clone_cache(self, max_age_hours: int = 24) -> int:
        """Clean up old cached repository clones.

        Args:
            max_age_hours: Maximum age of clones to keep.

        Returns:
            Number of clones removed.
        """
        removed = 0
        clone_dir = self._config.clone_dir

        if not clone_dir.exists():
            return 0

        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

        for repo_dir in clone_dir.iterdir():
            if not repo_dir.is_dir():
                continue

            try:
                mtime = repo_dir.stat().st_mtime
                if mtime < cutoff:
                    shutil.rmtree(repo_dir)
                    removed += 1
                    log.info("removed_stale_clone", path=str(repo_dir))
            except OSError as e:
                log.warning("cleanup_error", path=str(repo_dir), error=str(e))

        return removed
