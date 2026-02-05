"""Tests for IssueMatcher functionality."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from ai_issue_agent.config.schema import MatchingConfig
from ai_issue_agent.core.issue_matcher import (
    IssueMatcher,
    SearchError,
)
from ai_issue_agent.models.issue import Issue, IssueMatch, IssueSearchResult, IssueState
from ai_issue_agent.models.traceback import ParsedTraceback, StackFrame


@pytest.fixture
def matching_config() -> MatchingConfig:
    """Create a test matching configuration."""
    return MatchingConfig(
        confidence_threshold=0.85,
        max_search_results=20,
        include_closed=True,
        search_cache_ttl=300,
    )


@pytest.fixture
def mock_vcs() -> AsyncMock:
    """Create a mock VCS provider."""
    return AsyncMock()


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Create a mock LLM provider."""
    return AsyncMock()


@pytest.fixture
def issue_matcher(
    mock_vcs: AsyncMock,
    mock_llm: AsyncMock,
    matching_config: MatchingConfig,
) -> IssueMatcher:
    """Create an IssueMatcher instance for testing."""
    return IssueMatcher(mock_vcs, mock_llm, matching_config)


@pytest.fixture
def sample_traceback() -> ParsedTraceback:
    """Create a sample parsed traceback for testing."""
    return ParsedTraceback(
        exception_type="ValueError",
        exception_message="invalid literal for int() with base 10: 'abc'",
        frames=(
            StackFrame(
                file_path="/home/user/project/src/app/utils.py",
                line_number=42,
                function_name="parse_input",
                code_line="return int(value)",
            ),
            StackFrame(
                file_path="/home/user/project/src/app/main.py",
                line_number=15,
                function_name="process",
                code_line="result = parse_input(data)",
            ),
        ),
        raw_text="Traceback (most recent call last):\n...",
    )


@pytest.fixture
def sample_issue() -> Issue:
    """Create a sample issue for testing."""
    return Issue(
        number=123,
        title="ValueError in parse_input: invalid literal for int()",
        body="Error occurred when parsing user input in utils.py",
        url="https://github.com/owner/repo/issues/123",
        state=IssueState.OPEN,
        labels=("bug", "auto-triaged"),
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        updated_at=datetime(2026, 1, 2, 12, 0, 0),
        author="testuser",
    )


class TestIssueMatcher:
    """Tests for IssueMatcher class."""

    def test_init(
        self,
        issue_matcher: IssueMatcher,
        matching_config: MatchingConfig,
    ) -> None:
        """Test IssueMatcher initialization."""
        assert issue_matcher.confidence_threshold == matching_config.confidence_threshold
        assert issue_matcher._config == matching_config

    def test_build_search_query_basic(
        self,
        issue_matcher: IssueMatcher,
        sample_traceback: ParsedTraceback,
    ) -> None:
        """Test building a search query from traceback."""
        query = issue_matcher.build_search_query(sample_traceback)

        # Should include exception type
        assert "ValueError" in query

        # Should include function names from project frames
        assert "parse_input" in query or "process" in query

    def test_build_search_query_extracts_key_terms(
        self,
        issue_matcher: IssueMatcher,
    ) -> None:
        """Test that search query extracts key terms from message."""
        traceback = ParsedTraceback(
            exception_type="KeyError",
            exception_message="'user_id' not found in dictionary",
            frames=(),
            raw_text="",
        )

        query = issue_matcher.build_search_query(traceback)

        assert "KeyError" in query
        # 'dictionary' should be extracted, but common words filtered
        # 'not' and 'found' and 'in' should be filtered as stop words

    def test_extract_key_terms_filters_stop_words(
        self,
        issue_matcher: IssueMatcher,
    ) -> None:
        """Test that stop words are filtered from key terms."""
        terms = issue_matcher._extract_key_terms("the quick brown fox jumps over the lazy dog")

        # Common words should be filtered
        assert "the" not in terms
        assert "over" not in terms

        # Meaningful words should remain
        assert "quick" in terms
        assert "brown" in terms
        assert "jumps" in terms

    def test_extract_key_terms_handles_short_words(
        self,
        issue_matcher: IssueMatcher,
    ) -> None:
        """Test that short words are filtered."""
        terms = issue_matcher._extract_key_terms("a b cd xyz longer")

        # Short words (<=2 chars) should be filtered
        assert "a" not in terms
        assert "b" not in terms
        assert "cd" not in terms

        # Longer words should remain
        assert "xyz" in terms
        assert "longer" in terms

    @pytest.mark.asyncio
    async def test_find_matches_no_results(
        self,
        issue_matcher: IssueMatcher,
        mock_vcs: AsyncMock,
        sample_traceback: ParsedTraceback,
    ) -> None:
        """Test find_matches when no issues are found."""
        mock_vcs.search_issues.return_value = []

        matches = await issue_matcher.find_matches("owner/repo", sample_traceback)

        assert matches == []
        mock_vcs.search_issues.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_matches_with_results(
        self,
        issue_matcher: IssueMatcher,
        mock_vcs: AsyncMock,
        sample_traceback: ParsedTraceback,
        sample_issue: Issue,
    ) -> None:
        """Test find_matches with matching issues."""
        search_result = IssueSearchResult(
            issue=sample_issue,
            relevance_score=0.9,
            matched_terms=("ValueError", "parse_input"),
        )
        mock_vcs.search_issues.return_value = [search_result]

        matches = await issue_matcher.find_matches("owner/repo", sample_traceback)

        assert len(matches) > 0
        assert all(isinstance(m, IssueMatch) for m in matches)

    @pytest.mark.asyncio
    async def test_find_matches_respects_state_filter(
        self,
        mock_vcs: AsyncMock,
        mock_llm: AsyncMock,
    ) -> None:
        """Test that find_matches respects include_closed setting."""
        # Config with include_closed=False
        config = MatchingConfig(
            confidence_threshold=0.85,
            max_search_results=20,
            include_closed=False,
            search_cache_ttl=300,
        )
        matcher = IssueMatcher(mock_vcs, mock_llm, config)
        mock_vcs.search_issues.return_value = []

        traceback = ParsedTraceback(
            exception_type="TestError",
            exception_message="test",
            frames=(),
            raw_text="",
        )

        await matcher.find_matches("owner/repo", traceback)

        # Should search only open issues
        mock_vcs.search_issues.assert_called_once()
        call_kwargs = mock_vcs.search_issues.call_args.kwargs
        assert call_kwargs.get("state") == "open"

    @pytest.mark.asyncio
    async def test_find_matches_handles_search_error(
        self,
        issue_matcher: IssueMatcher,
        mock_vcs: AsyncMock,
        sample_traceback: ParsedTraceback,
    ) -> None:
        """Test that find_matches handles search errors gracefully."""
        mock_vcs.search_issues.side_effect = Exception("Search failed")

        with pytest.raises(SearchError) as exc_info:
            await issue_matcher.find_matches("owner/repo", sample_traceback)

        assert "Search failed" in str(exc_info.value)

    def test_calculate_exact_score_high_match(
        self,
        issue_matcher: IssueMatcher,
        sample_traceback: ParsedTraceback,
    ) -> None:
        """Test exact score calculation with high match."""
        issue = Issue(
            number=1,
            title="ValueError: invalid literal for int() with base 10",
            body="Error in parse_input function when converting string 'abc' to int",
            url="https://github.com/test/test/issues/1",
            state=IssueState.OPEN,
            labels=(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="test",
        )

        score = issue_matcher._calculate_exact_score(sample_traceback, issue)

        # Should have high score due to matching exception type and terms
        assert score > 0.5

    def test_calculate_exact_score_no_match(
        self,
        issue_matcher: IssueMatcher,
        sample_traceback: ParsedTraceback,
    ) -> None:
        """Test exact score calculation with no match."""
        issue = Issue(
            number=1,
            title="Completely unrelated issue about feature request",
            body="This is about adding a new feature to the UI",
            url="https://github.com/test/test/issues/1",
            state=IssueState.OPEN,
            labels=(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="test",
        )

        score = issue_matcher._calculate_exact_score(sample_traceback, issue)

        # Should have low score
        assert score < 0.5

    def test_calculate_stack_score_with_matching_files(
        self,
        issue_matcher: IssueMatcher,
        sample_traceback: ParsedTraceback,
    ) -> None:
        """Test stack score calculation with matching file names."""
        issue = Issue(
            number=1,
            title="Bug in utils.py",
            body="Error in parse_input function in utils.py at line 42",
            url="https://github.com/test/test/issues/1",
            state=IssueState.OPEN,
            labels=(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="test",
        )

        score = issue_matcher._calculate_stack_score(sample_traceback, issue)

        # Should have decent score due to matching file and function names
        assert score > 0.0

    def test_calculate_stack_score_no_project_frames(
        self,
        issue_matcher: IssueMatcher,
    ) -> None:
        """Test stack score with no project frames."""
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

        issue = Issue(
            number=1,
            title="Test issue",
            body="Test body",
            url="",
            state=IssueState.OPEN,
            labels=(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="test",
        )

        score = issue_matcher._calculate_stack_score(traceback, issue)

        # No project frames, should be 0
        assert score == 0.0

    def test_set_strategy_weight(
        self,
        issue_matcher: IssueMatcher,
    ) -> None:
        """Test setting strategy weights."""
        issue_matcher.set_strategy_weight("exact", 0.7)
        assert issue_matcher._strategies["exact"].weight == 0.7

    def test_set_strategy_weight_invalid_name(
        self,
        issue_matcher: IssueMatcher,
    ) -> None:
        """Test setting weight for invalid strategy name."""
        with pytest.raises(ValueError) as exc_info:
            issue_matcher.set_strategy_weight("invalid", 0.5)

        assert "Unknown strategy" in str(exc_info.value)

    def test_set_strategy_weight_negative(
        self,
        issue_matcher: IssueMatcher,
    ) -> None:
        """Test setting negative weight."""
        with pytest.raises(ValueError) as exc_info:
            issue_matcher.set_strategy_weight("exact", -0.5)

        assert "cannot be negative" in str(exc_info.value)

    def test_enable_strategy(
        self,
        issue_matcher: IssueMatcher,
    ) -> None:
        """Test enabling/disabling strategies."""
        issue_matcher.enable_strategy("semantic", False)
        assert issue_matcher._strategies["semantic"].enabled is False

        issue_matcher.enable_strategy("semantic", True)
        assert issue_matcher._strategies["semantic"].enabled is True

    def test_enable_strategy_invalid_name(
        self,
        issue_matcher: IssueMatcher,
    ) -> None:
        """Test enabling invalid strategy name."""
        with pytest.raises(ValueError) as exc_info:
            issue_matcher.enable_strategy("invalid", True)

        assert "Unknown strategy" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calculate_semantic_similarity(
        self,
        issue_matcher: IssueMatcher,
        mock_llm: AsyncMock,
        sample_traceback: ParsedTraceback,
        sample_issue: Issue,
    ) -> None:
        """Test semantic similarity calculation."""
        mock_llm.calculate_similarity.return_value = [
            (sample_issue, 0.85),
        ]

        result = await issue_matcher.calculate_semantic_similarity(
            sample_traceback,
            [sample_issue],
        )

        assert len(result) == 1
        assert result[0][0] == sample_issue
        assert result[0][1] == 0.85

    @pytest.mark.asyncio
    async def test_calculate_semantic_similarity_handles_error(
        self,
        issue_matcher: IssueMatcher,
        mock_llm: AsyncMock,
        sample_traceback: ParsedTraceback,
        sample_issue: Issue,
    ) -> None:
        """Test semantic similarity handles LLM errors gracefully."""
        mock_llm.calculate_similarity.side_effect = Exception("LLM error")

        result = await issue_matcher.calculate_semantic_similarity(
            sample_traceback,
            [sample_issue],
        )

        # Should return fallback scores
        assert len(result) == 1
        assert result[0][1] == 0.0

    @pytest.mark.asyncio
    async def test_calculate_semantic_similarity_empty_issues(
        self,
        issue_matcher: IssueMatcher,
        sample_traceback: ParsedTraceback,
    ) -> None:
        """Test semantic similarity with no issues."""
        result = await issue_matcher.calculate_semantic_similarity(
            sample_traceback,
            [],
        )

        assert result == []
