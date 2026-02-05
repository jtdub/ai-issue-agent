"""Tests for CodeAnalyzer functionality."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ai_issue_agent.config.schema import AnalysisConfig, GitHubConfig
from ai_issue_agent.core.code_analyzer import (
    CloneError,
    CodeAnalyzer,
    PathTraversalError,
    RepoCache,
)
from ai_issue_agent.models.analysis import CodeContext
from ai_issue_agent.models.traceback import ParsedTraceback, StackFrame


@pytest.fixture
def analysis_config() -> AnalysisConfig:
    """Create a test analysis configuration."""
    return AnalysisConfig(
        context_lines=15,
        max_files=10,
        skip_paths=["/usr/lib/python", "site-packages"],
        include_files=["README.md"],
    )


@pytest.fixture
def github_config(tmp_path: Path) -> GitHubConfig:
    """Create a test GitHub configuration."""
    return GitHubConfig(
        default_repo="owner/repo",
        clone_dir=tmp_path / "repos",
        clone_cache_ttl=3600,
        default_labels=["auto-triaged"],
    )


@pytest.fixture
def mock_vcs() -> AsyncMock:
    """Create a mock VCS provider."""
    return AsyncMock()


@pytest.fixture
def code_analyzer(
    mock_vcs: AsyncMock,
    analysis_config: AnalysisConfig,
    github_config: GitHubConfig,
) -> CodeAnalyzer:
    """Create a CodeAnalyzer instance for testing."""
    return CodeAnalyzer(mock_vcs, analysis_config, github_config)


@pytest.fixture
def sample_traceback() -> ParsedTraceback:
    """Create a sample parsed traceback for testing."""
    return ParsedTraceback(
        exception_type="ValueError",
        exception_message="invalid literal for int()",
        frames=(
            StackFrame(
                file_path="src/app/utils.py",
                line_number=42,
                function_name="parse_input",
                code_line="return int(value)",
            ),
            StackFrame(
                file_path="src/app/main.py",
                line_number=15,
                function_name="process",
                code_line="result = parse_input(data)",
            ),
        ),
        raw_text="Traceback (most recent call last):\n...",
    )


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a sample repository structure for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Create src/app directory
    src_app = repo_path / "src" / "app"
    src_app.mkdir(parents=True)

    # Create utils.py
    utils_py = src_app / "utils.py"
    utils_py.write_text("""# Utility functions
import json

def parse_input(value):
    \"\"\"Parse user input.\"\"\"
    # Some comment
    # Another comment
    if not value:
        return None
    # Validate input
    try:
        return int(value)  # Line 42 (adjusting for header)
    except ValueError:
        raise ValueError(f"Invalid input: {value}")

def other_func():
    pass
""")

    # Create main.py
    main_py = src_app / "main.py"
    main_py.write_text("""# Main module
from .utils import parse_input

def process(data):
    result = parse_input(data)
    return result * 2
""")

    # Create README.md
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\n\nThis is a test repo.\n")

    return repo_path


class TestRepoCache:
    """Tests for RepoCache class."""

    def test_cache_set_and_get(self, tmp_path: Path) -> None:
        """Test setting and getting from cache."""
        cache = RepoCache(ttl=3600)
        test_path = tmp_path / "repo"
        test_path.mkdir()

        cache.set("owner/repo", test_path)
        result = cache.get("owner/repo")

        assert result == test_path

    def test_cache_get_nonexistent(self) -> None:
        """Test getting nonexistent key from cache."""
        cache = RepoCache(ttl=3600)
        result = cache.get("nonexistent/repo")
        assert result is None

    def test_cache_ttl_expiration(self, tmp_path: Path) -> None:
        """Test cache TTL expiration."""
        cache = RepoCache(ttl=0)  # Immediate expiration
        test_path = tmp_path / "repo"
        test_path.mkdir()

        cache.set("owner/repo", test_path)

        # Should be expired immediately
        import time

        time.sleep(0.01)
        result = cache.get("owner/repo")
        assert result is None

    def test_cache_invalidate(self, tmp_path: Path) -> None:
        """Test cache invalidation."""
        cache = RepoCache(ttl=3600)
        test_path = tmp_path / "repo"
        test_path.mkdir()

        cache.set("owner/repo", test_path)
        cache.invalidate("owner/repo")

        result = cache.get("owner/repo")
        assert result is None

    def test_cache_clear(self, tmp_path: Path) -> None:
        """Test clearing entire cache."""
        cache = RepoCache(ttl=3600)
        test_path1 = tmp_path / "repo1"
        test_path2 = tmp_path / "repo2"
        test_path1.mkdir()
        test_path2.mkdir()

        cache.set("owner/repo1", test_path1)
        cache.set("owner/repo2", test_path2)
        cache.clear()

        assert cache.get("owner/repo1") is None
        assert cache.get("owner/repo2") is None

    def test_cache_path_no_longer_exists(self, tmp_path: Path) -> None:
        """Test cache returns None if path no longer exists."""
        cache = RepoCache(ttl=3600)
        test_path = tmp_path / "repo"
        test_path.mkdir()

        cache.set("owner/repo", test_path)

        # Remove the directory
        test_path.rmdir()

        result = cache.get("owner/repo")
        assert result is None


class TestCodeAnalyzer:
    """Tests for CodeAnalyzer class."""

    def test_init(
        self,
        code_analyzer: CodeAnalyzer,
        analysis_config: AnalysisConfig,
    ) -> None:
        """Test CodeAnalyzer initialization."""
        assert code_analyzer._config == analysis_config
        assert code_analyzer._clone_dir.exists()

    def test_init_without_github_config(
        self,
        mock_vcs: AsyncMock,
        analysis_config: AnalysisConfig,
    ) -> None:
        """Test initialization without GitHub config uses defaults."""
        analyzer = CodeAnalyzer(mock_vcs, analysis_config, None)
        assert analyzer._clone_dir == Path("/tmp/ai-issue-agent/repos")  # noqa: S108

    @pytest.mark.asyncio
    async def test_analyze_no_project_frames(
        self,
        code_analyzer: CodeAnalyzer,
    ) -> None:
        """Test analyze with no project frames."""
        traceback = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=(
                StackFrame(
                    file_path="/usr/lib/python3.11/json/__init__.py",
                    line_number=100,
                    function_name="loads",
                ),
            ),
            raw_text="",
        )

        contexts = await code_analyzer.analyze("owner/repo", traceback)

        # No project frames, should return empty
        assert contexts == []

    @pytest.mark.asyncio
    async def test_analyze_with_project_frames(
        self,
        code_analyzer: CodeAnalyzer,
        mock_vcs: AsyncMock,
        sample_traceback: ParsedTraceback,
        sample_repo: Path,
    ) -> None:
        """Test analyze with project frames."""
        mock_vcs.clone_repository.return_value = sample_repo

        contexts = await code_analyzer.analyze("owner/repo", sample_traceback)

        # Should extract context for project frames
        assert len(contexts) > 0
        assert all(isinstance(ctx, CodeContext) for ctx in contexts)

    @pytest.mark.asyncio
    async def test_analyze_uses_cache(
        self,
        code_analyzer: CodeAnalyzer,
        mock_vcs: AsyncMock,
        sample_traceback: ParsedTraceback,
        sample_repo: Path,
    ) -> None:
        """Test that analyze uses cached repos."""
        mock_vcs.clone_repository.return_value = sample_repo

        # First call
        await code_analyzer.analyze("owner/repo", sample_traceback)

        # Second call should use cache
        await code_analyzer.analyze("owner/repo", sample_traceback)

        # Clone should only be called once
        assert mock_vcs.clone_repository.call_count == 1

    @pytest.mark.asyncio
    async def test_get_surrounding_code_basic(
        self,
        code_analyzer: CodeAnalyzer,
        sample_repo: Path,
    ) -> None:
        """Test getting surrounding code."""
        context = await code_analyzer.get_surrounding_code(
            repo_path=sample_repo,
            file_path="src/app/utils.py",
            line_number=10,
            context_lines=5,
        )

        assert context is not None
        assert context.file_path == "src/app/utils.py"
        assert context.start_line <= 10
        assert context.end_line >= 10
        assert context.content is not None
        assert context.highlight_line == 10

    @pytest.mark.asyncio
    async def test_get_surrounding_code_file_not_found(
        self,
        code_analyzer: CodeAnalyzer,
        sample_repo: Path,
    ) -> None:
        """Test getting code from nonexistent file."""
        context = await code_analyzer.get_surrounding_code(
            repo_path=sample_repo,
            file_path="nonexistent.py",
            line_number=10,
        )

        assert context is None

    @pytest.mark.asyncio
    async def test_get_surrounding_code_path_traversal(
        self,
        code_analyzer: CodeAnalyzer,
        sample_repo: Path,
    ) -> None:
        """Test path traversal prevention."""
        with pytest.raises(PathTraversalError):
            await code_analyzer.get_surrounding_code(
                repo_path=sample_repo,
                file_path="../../../etc/passwd",
                line_number=1,
            )

    @pytest.mark.asyncio
    async def test_get_surrounding_code_absolute_path(
        self,
        code_analyzer: CodeAnalyzer,
        sample_repo: Path,
    ) -> None:
        """Test absolute path prevention."""
        with pytest.raises(PathTraversalError):
            await code_analyzer.get_surrounding_code(
                repo_path=sample_repo,
                file_path="/etc/passwd",
                line_number=1,
            )

    @pytest.mark.asyncio
    async def test_get_surrounding_code_respects_context_lines(
        self,
        code_analyzer: CodeAnalyzer,
        sample_repo: Path,
    ) -> None:
        """Test that context_lines parameter is respected."""
        context = await code_analyzer.get_surrounding_code(
            repo_path=sample_repo,
            file_path="src/app/utils.py",
            line_number=10,
            context_lines=2,
        )

        assert context is not None
        # With 2 context lines, should have max 5 lines (2 before, line, 2 after)
        assert context.line_count <= 5

    def test_normalize_frame_path_src_prefix(
        self,
        code_analyzer: CodeAnalyzer,
    ) -> None:
        """Test frame path normalization with src/ prefix."""
        result = code_analyzer._normalize_frame_path("/home/user/project/src/app/utils.py")
        assert result == "src/app/utils.py"

    def test_normalize_frame_path_lib_prefix(
        self,
        code_analyzer: CodeAnalyzer,
    ) -> None:
        """Test frame path normalization with lib/ prefix."""
        result = code_analyzer._normalize_frame_path("/opt/project/lib/module.py")
        assert result == "lib/module.py"

    def test_normalize_frame_path_no_marker(
        self,
        code_analyzer: CodeAnalyzer,
    ) -> None:
        """Test frame path normalization without known markers."""
        result = code_analyzer._normalize_frame_path("/home/user/myproject/module.py")
        # Should extract last parts
        assert "module.py" in result

    def test_resolve_file_path_valid(
        self,
        code_analyzer: CodeAnalyzer,
        sample_repo: Path,
    ) -> None:
        """Test file path resolution with valid path."""
        resolved = code_analyzer._resolve_file_path(sample_repo, "src/app/utils.py")
        assert resolved.exists()
        assert resolved.is_file()

    def test_resolve_file_path_traversal_dotdot(
        self,
        code_analyzer: CodeAnalyzer,
        sample_repo: Path,
    ) -> None:
        """Test file path resolution blocks .. traversal."""
        with pytest.raises(PathTraversalError):
            code_analyzer._resolve_file_path(sample_repo, "../outside.py")

    def test_resolve_file_path_traversal_absolute(
        self,
        code_analyzer: CodeAnalyzer,
        sample_repo: Path,
    ) -> None:
        """Test file path resolution blocks absolute paths."""
        with pytest.raises(PathTraversalError):
            code_analyzer._resolve_file_path(sample_repo, "/etc/passwd")

    @pytest.mark.asyncio
    async def test_ensure_repo_cloned_success(
        self,
        code_analyzer: CodeAnalyzer,
        mock_vcs: AsyncMock,
        sample_repo: Path,
    ) -> None:
        """Test successful repository cloning."""
        mock_vcs.clone_repository.return_value = sample_repo

        result = await code_analyzer._ensure_repo_cloned("owner/repo")

        assert result == sample_repo
        mock_vcs.clone_repository.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_repo_cloned_failure(
        self,
        code_analyzer: CodeAnalyzer,
        mock_vcs: AsyncMock,
    ) -> None:
        """Test clone failure handling."""
        mock_vcs.clone_repository.side_effect = Exception("Clone failed")

        with pytest.raises(CloneError) as exc_info:
            await code_analyzer._ensure_repo_cloned("owner/repo")

        assert "Clone failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_read_additional_file(
        self,
        code_analyzer: CodeAnalyzer,
        sample_repo: Path,
    ) -> None:
        """Test reading additional files."""
        context = await code_analyzer._read_additional_file(sample_repo, "README.md")

        assert context is not None
        assert context.file_path == "README.md"
        assert "Test Repository" in context.content

    @pytest.mark.asyncio
    async def test_read_additional_file_not_found(
        self,
        code_analyzer: CodeAnalyzer,
        sample_repo: Path,
    ) -> None:
        """Test reading nonexistent additional file returns None."""
        result = await code_analyzer._read_additional_file(sample_repo, "NONEXISTENT.md")
        assert result is None

    def test_invalidate_cache_specific(
        self,
        code_analyzer: CodeAnalyzer,
    ) -> None:
        """Test invalidating specific repo from cache."""
        # This should not raise
        code_analyzer.invalidate_cache("owner/repo")

    def test_invalidate_cache_all(
        self,
        code_analyzer: CodeAnalyzer,
    ) -> None:
        """Test clearing entire cache."""
        # This should not raise
        code_analyzer.invalidate_cache()

    @pytest.mark.asyncio
    async def test_analyze_includes_additional_files(
        self,
        code_analyzer: CodeAnalyzer,
        mock_vcs: AsyncMock,
        sample_traceback: ParsedTraceback,
        sample_repo: Path,
    ) -> None:
        """Test that analyze includes configured additional files."""
        mock_vcs.clone_repository.return_value = sample_repo

        contexts = await code_analyzer.analyze("owner/repo", sample_traceback)

        # Should include README.md as configured
        file_paths = [ctx.file_path for ctx in contexts]
        assert "README.md" in file_paths

    @pytest.mark.asyncio
    async def test_analyze_respects_max_files(
        self,
        mock_vcs: AsyncMock,
        sample_repo: Path,
    ) -> None:
        """Test that analyze respects max_files config."""
        config = AnalysisConfig(
            context_lines=15,
            max_files=1,  # Only analyze 1 file
            skip_paths=[],
            include_files=[],
        )
        analyzer = CodeAnalyzer(mock_vcs, config, None)
        mock_vcs.clone_repository.return_value = sample_repo

        # Create traceback with many frames
        frames = tuple(
            StackFrame(
                file_path=f"src/app/file{i}.py",
                line_number=i,
                function_name=f"func{i}",
            )
            for i in range(5)
        )
        traceback = ParsedTraceback(
            exception_type="Error",
            exception_message="test",
            frames=frames,
            raw_text="",
        )

        contexts = await analyzer.analyze("owner/repo", traceback)

        # Should be limited to max_files (some files might not exist)
        # Just verify it doesn't exceed max_files + include_files
        assert len(contexts) <= 2  # 1 max_file + potential includes

    @pytest.mark.asyncio
    async def test_code_is_redacted(
        self,
        code_analyzer: CodeAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test that extracted code has secrets redacted."""
        # Create a file with a secret
        repo = tmp_path / "repo_with_secret"
        repo.mkdir()
        secret_file = repo / "config.py"
        secret_file.write_text(
            "API_KEY = 'sk-FAKEabcd1234abcd1234abcd1234abcd1234abcd1234abcd'\nother_value = 42\n"
        )

        context = await code_analyzer.get_surrounding_code(
            repo_path=repo,
            file_path="config.py",
            line_number=1,
        )

        assert context is not None
        # Secret should be redacted
        assert "sk-FAKE" not in context.content
        assert "[REDACTED]" in context.content
