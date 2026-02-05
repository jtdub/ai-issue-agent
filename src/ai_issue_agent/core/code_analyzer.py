"""Code analysis to extract context from repositories for LLM analysis.

This module implements the CodeAnalyzer class that extracts code context
from repositories for traceback analysis. It handles:
- Repository cloning and caching
- Code extraction for stack frame locations
- Security validation (path traversal prevention)
- Secret redaction in extracted code

See docs/ARCHITECTURE.md for the canonical design.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from ai_issue_agent.config.schema import AnalysisConfig, GitHubConfig
from ai_issue_agent.models.analysis import CodeContext
from ai_issue_agent.models.traceback import ParsedTraceback
from ai_issue_agent.utils.security import SecretRedactor

if TYPE_CHECKING:
    from ai_issue_agent.interfaces.vcs import VCSProvider

log = structlog.get_logger()


class CodeAnalyzerError(Exception):
    """Base exception for code analyzer errors."""


class CloneError(CodeAnalyzerError):
    """Failed to clone repository."""


class FileReadError(CodeAnalyzerError):
    """Failed to read file from repository."""


class PathTraversalError(CodeAnalyzerError):
    """Detected path traversal attempt."""


class RepoCache:
    """Simple cache for cloned repositories.

    Tracks when repositories were cloned and manages TTL expiration.
    """

    def __init__(self, ttl: int = 3600) -> None:
        """Initialize the cache.

        Args:
            ttl: Time-to-live in seconds for cached clones
        """
        self._ttl = ttl
        self._cache: dict[str, tuple[Path, float]] = {}

    def get(self, repo: str) -> Path | None:
        """Get cached repository path if valid.

        Args:
            repo: Repository identifier

        Returns:
            Path to cached repo, or None if not cached or expired
        """
        if repo not in self._cache:
            return None

        path, timestamp = self._cache[repo]

        # Check TTL
        if time.time() - timestamp > self._ttl:
            # Expired
            del self._cache[repo]
            return None

        # Check if path still exists
        if not path.exists():
            del self._cache[repo]
            return None

        return path

    def set(self, repo: str, path: Path) -> None:
        """Cache a repository path.

        Args:
            repo: Repository identifier
            path: Path to the cloned repository
        """
        self._cache[repo] = (path, time.time())

    def invalidate(self, repo: str) -> None:
        """Invalidate a cached repository.

        Args:
            repo: Repository identifier
        """
        self._cache.pop(repo, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()


class CodeAnalyzer:
    """Analyzes repository code related to a traceback.

    Responsibilities:
    - Clone repository (if needed)
    - Extract code context for stack frame locations
    - Gather additional context (imports, related files)
    - Prepare code for LLM analysis

    Security:
    - Uses SafeGHCli for clone operations
    - Validates file paths (no path traversal)
    - Applies SecretRedactor to extracted code

    Example:
        analyzer = CodeAnalyzer(vcs, analysis_config, github_config)
        contexts = await analyzer.analyze("owner/repo", traceback)
    """

    def __init__(
        self,
        vcs: VCSProvider,
        config: AnalysisConfig,
        github_config: GitHubConfig | None = None,
    ) -> None:
        """Initialize the CodeAnalyzer.

        Args:
            vcs: VCS provider for repository operations
            config: Analysis configuration
            github_config: GitHub-specific configuration (for clone directory)
        """
        self._vcs = vcs
        self._config = config

        # Set up clone directory
        if github_config:
            self._clone_dir = github_config.clone_dir
            cache_ttl = github_config.clone_cache_ttl
        else:
            self._clone_dir = Path("/tmp/ai-issue-agent/repos")  # noqa: S108
            cache_ttl = 3600

        # Ensure clone directory exists
        self._clone_dir.mkdir(parents=True, exist_ok=True)

        # Initialize cache and redactor
        self._cache = RepoCache(ttl=cache_ttl)
        self._redactor = SecretRedactor()

    async def analyze(
        self,
        repo: str,
        traceback: ParsedTraceback,
    ) -> list[CodeContext]:
        """Extract code context for all stack frames.

        Args:
            repo: Repository identifier (e.g., "owner/repo")
            traceback: Parsed traceback with stack frames

        Returns:
            List of code contexts for each relevant file

        Raises:
            CodeAnalyzerError: If analysis fails
        """
        log.info(
            "analyzing_code_context",
            repo=repo,
            frames_count=len(traceback.frames),
            project_frames_count=len(traceback.project_frames),
        )

        # Get project frames only (skip stdlib and site-packages)
        project_frames = traceback.project_frames

        if not project_frames:
            log.warning("no_project_frames", repo=repo)
            return []

        # Limit number of files to analyze
        frames_to_analyze = project_frames[: self._config.max_files]

        # Clone repository if needed
        repo_path = await self._ensure_repo_cloned(repo)

        # Extract code context for each frame
        contexts: list[CodeContext] = []
        seen_files: set[str] = set()

        for frame in frames_to_analyze:
            # Skip if we've already processed this file
            normalized_path = self._normalize_frame_path(frame.file_path)
            if normalized_path in seen_files:
                continue
            seen_files.add(normalized_path)

            try:
                context = await self.get_surrounding_code(
                    repo_path=repo_path,
                    file_path=normalized_path,
                    line_number=frame.line_number,
                    context_lines=self._config.context_lines,
                )
                if context:
                    contexts.append(context)
            except (FileReadError, PathTraversalError) as e:
                log.warning(
                    "frame_context_extraction_failed",
                    file_path=normalized_path,
                    error=str(e),
                )
                continue

        # Include additional files if configured
        for include_file in self._config.include_files:
            if include_file not in seen_files:
                try:
                    context = await self._read_additional_file(repo_path, include_file)
                    if context:
                        contexts.append(context)
                except FileReadError:
                    pass  # Additional files are optional

        log.info(
            "code_context_extracted",
            repo=repo,
            contexts_count=len(contexts),
        )

        return contexts

    async def get_surrounding_code(
        self,
        repo_path: Path,
        file_path: str,
        line_number: int,
        context_lines: int | None = None,
    ) -> CodeContext | None:
        """Get code surrounding a specific line.

        Args:
            repo_path: Path to the cloned repository
            file_path: Relative path to the file within the repository
            line_number: Line number to center context around (1-indexed)
            context_lines: Number of lines before/after (default from config)

        Returns:
            CodeContext with surrounding code, or None if file not found

        Raises:
            PathTraversalError: If path traversal is detected
            FileReadError: If file cannot be read
        """
        if context_lines is None:
            context_lines = self._config.context_lines

        # Validate and resolve file path
        full_path = self._resolve_file_path(repo_path, file_path)

        if not full_path.exists():
            log.debug("file_not_found", file_path=file_path)
            return None

        if not full_path.is_file():
            log.debug("path_not_a_file", file_path=file_path)
            return None

        try:
            # Read file content
            content = full_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            if not lines:
                return None

            # Calculate line range (1-indexed)
            total_lines = len(lines)
            start_line = max(1, line_number - context_lines)
            end_line = min(total_lines, line_number + context_lines)

            # Extract relevant lines (convert to 0-indexed for slicing)
            extracted_lines = lines[start_line - 1 : end_line]
            extracted_content = "\n".join(extracted_lines)

            # Apply secret redaction
            redacted_content = self._redactor.redact(extracted_content)

            return CodeContext(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                content=redacted_content,
                highlight_line=line_number if start_line <= line_number <= end_line else None,
            )

        except OSError as e:
            raise FileReadError(f"Failed to read {file_path}: {e}") from e

    async def _ensure_repo_cloned(self, repo: str) -> Path:
        """Ensure repository is cloned locally.

        Args:
            repo: Repository identifier

        Returns:
            Path to the cloned repository

        Raises:
            CloneError: If cloning fails
        """
        # Check cache first
        cached_path = self._cache.get(repo)
        if cached_path:
            log.debug("using_cached_repo", repo=repo, path=str(cached_path))
            return cached_path

        # Prepare destination path
        # Use sanitized repo name as directory
        safe_name = repo.replace("/", "_")
        destination = self._clone_dir / safe_name

        try:
            # Clone the repository
            log.info("cloning_repository", repo=repo, destination=str(destination))
            path = await self._vcs.clone_repository(
                repo=repo,
                destination=destination,
                shallow=True,  # Use shallow clone for performance
            )

            # Cache the result
            self._cache.set(repo, path)

            return path

        except Exception as e:
            log.error("clone_failed", repo=repo, error=str(e))
            raise CloneError(f"Failed to clone {repo}: {e}") from e

    def _resolve_file_path(self, repo_path: Path, file_path: str) -> Path:
        """Resolve and validate a file path within the repository.

        Args:
            repo_path: Path to the repository root
            file_path: Relative path to resolve

        Returns:
            Absolute path to the file

        Raises:
            PathTraversalError: If path traversal is detected
        """
        # Normalize and join paths
        normalized = os.path.normpath(file_path)

        # Check for path traversal attempts
        if normalized.startswith("..") or normalized.startswith("/"):
            raise PathTraversalError(f"Invalid file path: {file_path}")

        full_path = (repo_path / normalized).resolve()

        # Ensure the resolved path is within the repository
        try:
            full_path.relative_to(repo_path.resolve())
        except ValueError:
            raise PathTraversalError(f"Path traversal detected: {file_path}") from None

        return full_path

    def _normalize_frame_path(self, frame_path: str) -> str:
        """Normalize a frame path for repository lookup.

        Strips common prefixes and normalizes path separators.

        Args:
            frame_path: Original path from stack frame

        Returns:
            Normalized relative path
        """
        path = frame_path

        # Handle common patterns in stack traces
        # Look for common project directory patterns
        markers = ["src/", "lib/", "app/", "pkg/"]

        for marker in markers:
            if marker in path:
                idx = path.find(marker)
                path = path[idx:]
                break
        else:
            # If no marker found, try to extract a reasonable relative path
            # Remove leading slashes and common prefixes
            parts = path.replace("\\", "/").split("/")

            # Skip common absolute path prefixes
            skip_prefixes = {"home", "Users", "usr", "var", "opt", "tmp"}

            cleaned_parts: list[str] = []
            skipping = True
            for part in parts:
                if skipping and (not part or part in skip_prefixes):
                    continue
                skipping = False
                cleaned_parts.append(part)

            if cleaned_parts:
                path = "/".join(cleaned_parts)

        return path

    async def _read_additional_file(
        self,
        repo_path: Path,
        file_name: str,
    ) -> CodeContext | None:
        """Read an additional file from the repository.

        Args:
            repo_path: Path to the repository
            file_name: Name of the file to read

        Returns:
            CodeContext with file content, or None if not found
        """
        try:
            full_path = self._resolve_file_path(repo_path, file_name)

            if not full_path.exists() or not full_path.is_file():
                return None

            content = full_path.read_text(encoding="utf-8", errors="replace")

            # Limit content size for large files
            max_chars = 10000  # Reasonable limit for additional context
            if len(content) > max_chars:
                content = content[:max_chars] + "\n... (truncated)"

            # Apply secret redaction
            redacted_content = self._redactor.redact(content)

            lines = redacted_content.splitlines()

            return CodeContext(
                file_path=file_name,
                start_line=1,
                end_line=len(lines),
                content=redacted_content,
                highlight_line=None,
            )

        except (OSError, PathTraversalError) as e:
            log.debug("additional_file_read_failed", file=file_name, error=str(e))
            raise FileReadError(f"Failed to read {file_name}: {e}") from e

    def invalidate_cache(self, repo: str | None = None) -> None:
        """Invalidate cached repositories.

        Args:
            repo: Specific repository to invalidate, or None to clear all
        """
        if repo:
            self._cache.invalidate(repo)
            log.info("cache_invalidated", repo=repo)
        else:
            self._cache.clear()
            log.info("cache_cleared")
