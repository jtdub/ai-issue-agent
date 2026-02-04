"""Abstract interface for version control system integrations."""

from pathlib import Path
from typing import Protocol

from ..models.issue import Issue, IssueCreate, IssueSearchResult


class VCSProvider(Protocol):
    """Abstract interface for version control system integrations.

    This protocol defines the contract that all VCS adapters
    (GitHub, GitLab, Bitbucket, etc.) must implement.
    """

    async def search_issues(
        self,
        repo: str,
        query: str,
        state: str = "all",
        max_results: int = 10,
    ) -> list[IssueSearchResult]:
        """
        Search for issues matching the query.

        Args:
            repo: Repository identifier (e.g., "owner/repo")
            query: Search query string
            state: Filter by issue state: "open", "closed", or "all"
            max_results: Maximum number of results to return

        Returns:
            List of matching issues with relevance scores

        Raises:
            SearchError: If search fails
            AuthenticationError: If not authorized
            RateLimitError: If rate limit exceeded
        """
        ...

    async def get_issue(
        self,
        repo: str,
        issue_number: int,
    ) -> Issue | None:
        """
        Fetch a specific issue by number.

        Args:
            repo: Repository identifier (e.g., "owner/repo")
            issue_number: Issue number

        Returns:
            Issue if found, None otherwise

        Raises:
            AuthenticationError: If not authorized
            NotFoundError: If repository doesn't exist
        """
        ...

    async def create_issue(
        self,
        repo: str,
        issue: IssueCreate,
    ) -> Issue:
        """
        Create a new issue in the repository.

        Args:
            repo: Repository identifier (e.g., "owner/repo")
            issue: Issue creation data (title, body, labels, assignees)

        Returns:
            The created issue with assigned number and URL

        Raises:
            CreateError: If issue creation fails
            AuthenticationError: If not authorized
            ValidationError: If issue data is invalid
        """
        ...

    async def clone_repository(
        self,
        repo: str,
        destination: Path,
        branch: str | None = None,
        shallow: bool = True,
    ) -> Path:
        """
        Clone a repository to a local directory.

        Security: This method MUST disable git hooks and use
        secure clone options. See SafeGHCli for implementation.

        Args:
            repo: Repository identifier (e.g., "owner/repo")
            destination: Local directory path
            branch: Specific branch to clone (default: default branch)
            shallow: If True, perform shallow clone (--depth 1)

        Returns:
            Path to the cloned repository

        Raises:
            CloneError: If cloning fails
            AuthenticationError: If not authorized
            SecurityError: If repository validation fails
        """
        ...

    async def get_file_content(
        self,
        repo: str,
        file_path: str,
        ref: str | None = None,
    ) -> str | None:
        """
        Fetch content of a file from the repository.

        Useful for reading files without full clone.

        Args:
            repo: Repository identifier (e.g., "owner/repo")
            file_path: Path to file within repository
            ref: Git reference (branch, tag, or commit; default: default branch HEAD)

        Returns:
            File contents as string, None if file doesn't exist

        Raises:
            AuthenticationError: If not authorized
            NotFoundError: If repository doesn't exist
        """
        ...

    async def get_default_branch(self, repo: str) -> str:
        """
        Get the default branch name for a repository.

        Args:
            repo: Repository identifier (e.g., "owner/repo")

        Returns:
            Default branch name (e.g., "main", "master")

        Raises:
            AuthenticationError: If not authorized
            NotFoundError: If repository doesn't exist
        """
        ...
