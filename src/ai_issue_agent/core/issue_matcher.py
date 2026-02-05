"""Issue matching logic to find existing issues for tracebacks.

This module implements the IssueMatcher class that finds existing issues
matching a given traceback using multiple strategies:
1. Exact match - same exception type and message
2. Similar stack trace - overlapping file/function names
3. Semantic similarity - LLM-based comparison

See docs/ARCHITECTURE.md for the canonical design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from ai_issue_agent.config.schema import MatchingConfig
from ai_issue_agent.models.issue import Issue, IssueMatch, IssueSearchResult
from ai_issue_agent.models.traceback import ParsedTraceback

if TYPE_CHECKING:
    from ai_issue_agent.interfaces.llm import LLMProvider
    from ai_issue_agent.interfaces.vcs import VCSProvider

log = structlog.get_logger()


class IssueMatcherError(Exception):
    """Base exception for issue matching errors."""


class SearchError(IssueMatcherError):
    """Failed to search for issues."""


@dataclass
class MatchStrategy:
    """Configuration for a matching strategy."""

    name: str
    weight: float
    enabled: bool = True


class IssueMatcher:
    """Finds existing issues that match a traceback.

    Responsibilities:
    - Build search queries from parsed tracebacks
    - Search VCS issues using multiple strategies
    - Score and rank potential matches
    - Determine if a match is "close enough"

    Matching Strategies:
    1. Exact exception match: Same exception type and message
    2. Similar stack trace: Overlapping file/function names
    3. Semantic similarity: LLM-based similarity scoring

    Example:
        matcher = IssueMatcher(vcs, llm, config)
        matches = await matcher.find_matches("owner/repo", traceback)
        if matches and matches[0].confidence >= config.confidence_threshold:
            # Link to existing issue
            pass
    """

    # Default weights for matching strategies
    DEFAULT_EXACT_WEIGHT = 0.5
    DEFAULT_STACK_WEIGHT = 0.3
    DEFAULT_SEMANTIC_WEIGHT = 0.2

    def __init__(
        self,
        vcs: VCSProvider,
        llm: LLMProvider,
        config: MatchingConfig,
    ) -> None:
        """Initialize the IssueMatcher.

        Args:
            vcs: VCS provider for searching issues
            llm: LLM provider for semantic similarity
            config: Matching configuration
        """
        self._vcs = vcs
        self._llm = llm
        self._config = config

        # Initialize strategies with default weights
        self._strategies: dict[str, MatchStrategy] = {
            "exact": MatchStrategy("exact", self.DEFAULT_EXACT_WEIGHT),
            "stack": MatchStrategy("stack", self.DEFAULT_STACK_WEIGHT),
            "semantic": MatchStrategy("semantic", self.DEFAULT_SEMANTIC_WEIGHT),
        }

    @property
    def confidence_threshold(self) -> float:
        """Return the confidence threshold for matches."""
        return self._config.confidence_threshold

    async def find_matches(
        self,
        repo: str,
        traceback: ParsedTraceback,
    ) -> list[IssueMatch]:
        """Find existing issues matching the traceback.

        Args:
            repo: Repository identifier (e.g., "owner/repo")
            traceback: Parsed traceback to match

        Returns:
            List of matches with confidence scores, sorted by confidence descending

        Raises:
            SearchError: If the search operation fails
        """
        log.info(
            "searching_for_matching_issues",
            repo=repo,
            exception_type=traceback.exception_type,
        )

        try:
            # Build search query
            query = self.build_search_query(traceback)

            # Determine state filter
            state = "all" if self._config.include_closed else "open"

            # Search for issues
            search_results = await self._vcs.search_issues(
                repo=repo,
                query=query,
                state=state,
                max_results=self._config.max_search_results,
            )

            if not search_results:
                log.info("no_issues_found", repo=repo)
                return []

            # Extract issues from search results
            issues = [result.issue for result in search_results]

            # Score each issue using multiple strategies
            matches = await self._score_issues(traceback, issues, search_results)

            # Filter by threshold and sort by confidence
            filtered_matches = [
                match
                for match in matches
                if match.confidence
                >= self._config.confidence_threshold * 0.5  # Return lower matches for context
            ]
            filtered_matches.sort(key=lambda m: m.confidence, reverse=True)

            log.info(
                "found_matching_issues",
                repo=repo,
                total_searched=len(issues),
                matches_found=len(filtered_matches),
            )

            return filtered_matches

        except Exception as e:
            log.error("issue_search_failed", repo=repo, error=str(e))
            raise SearchError(f"Failed to search issues: {e}") from e

    def build_search_query(self, traceback: ParsedTraceback) -> str:
        """Build a search query string from traceback data.

        Creates a search query optimized for finding similar issues.
        Includes exception type, key parts of the message, and
        relevant file/function names.

        Args:
            traceback: Parsed traceback to build query from

        Returns:
            Search query string
        """
        query_parts: list[str] = []

        # Add exception type
        query_parts.append(traceback.exception_type)

        # Extract key words from exception message
        # Skip common words and keep significant terms
        message_words = self._extract_key_terms(traceback.exception_message)
        if message_words:
            query_parts.extend(message_words[:5])  # Limit to 5 key terms

        # Add function names from project frames
        for frame in traceback.project_frames[:3]:  # Top 3 project frames
            if frame.function_name and frame.function_name not in ("<module>", "<lambda>"):
                query_parts.append(frame.function_name)

        # Build the query string
        query = " ".join(query_parts)

        log.debug("built_search_query", query=query)
        return query

    def _extract_key_terms(self, message: str) -> list[str]:
        """Extract significant terms from an exception message.

        Filters out common stop words and short terms.

        Args:
            message: Exception message to extract terms from

        Returns:
            List of significant terms
        """
        # Common words to skip
        stop_words = frozenset(
            [
                "the",
                "a",
                "an",
                "is",
                "are",
                "was",
                "were",
                "be",
                "been",
                "being",
                "have",
                "has",
                "had",
                "do",
                "does",
                "did",
                "will",
                "would",
                "could",
                "should",
                "may",
                "might",
                "must",
                "shall",
                "can",
                "need",
                "to",
                "of",
                "in",
                "for",
                "on",
                "with",
                "at",
                "by",
                "from",
                "as",
                "into",
                "through",
                "during",
                "before",
                "after",
                "above",
                "below",
                "between",
                "under",
                "over",
                "again",
                "further",
                "then",
                "once",
                "here",
                "there",
                "when",
                "where",
                "why",
                "how",
                "all",
                "each",
                "few",
                "more",
                "most",
                "other",
                "some",
                "such",
                "no",
                "nor",
                "not",
                "only",
                "own",
                "same",
                "so",
                "than",
                "too",
                "very",
                "just",
                "but",
                "and",
                "or",
                "if",
                "because",
                "until",
                "while",
                "got",
                "invalid",
                "error",
                "failed",
                "cannot",
            ]
        )

        # Split and filter
        words = message.lower().replace("'", " ").replace('"', " ").split()
        terms = [
            word.strip(".,;:!?()[]{}'\"-")
            for word in words
            if len(word) > 2 and word.lower() not in stop_words
        ]

        return terms

    async def _score_issues(
        self,
        traceback: ParsedTraceback,
        issues: list[Issue],
        search_results: list[IssueSearchResult],
    ) -> list[IssueMatch]:
        """Score issues using multiple matching strategies.

        Args:
            traceback: Parsed traceback to match
            issues: Issues to score
            search_results: Original search results with relevance scores

        Returns:
            List of IssueMatch objects with combined scores
        """
        # Build lookup for search relevance scores
        relevance_map = {result.issue.number: result.relevance_score for result in search_results}

        # Score each issue
        matches: list[IssueMatch] = []

        for issue in issues:
            # Calculate scores for each strategy
            exact_score = self._calculate_exact_score(traceback, issue)
            stack_score = self._calculate_stack_score(traceback, issue)
            search_relevance = relevance_map.get(issue.number, 0.0)

            # Combine scores using weights
            combined_score = (
                exact_score * self._strategies["exact"].weight
                + stack_score * self._strategies["stack"].weight
                + search_relevance * self._strategies["semantic"].weight
            )

            # Collect match reasons
            reasons: list[str] = []
            if exact_score > 0.8:
                reasons.append("exact_exception_match")
            elif exact_score > 0.5:
                reasons.append("similar_exception_type")
            if stack_score > 0.5:
                reasons.append("overlapping_stack_frames")
            if search_relevance > 0.7:
                reasons.append("high_search_relevance")

            if not reasons:
                reasons.append("partial_match")

            matches.append(
                IssueMatch(
                    issue=issue,
                    confidence=min(combined_score, 1.0),
                    match_reasons=tuple(reasons),
                )
            )

        return matches

    def _calculate_exact_score(
        self,
        traceback: ParsedTraceback,
        issue: Issue,
    ) -> float:
        """Calculate exact match score.

        Compares exception type and message with issue title and body.

        Args:
            traceback: Parsed traceback
            issue: Issue to compare against

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0
        issue_text = f"{issue.title} {issue.body}".lower()
        exception_type_lower = traceback.exception_type.lower()

        # Check for exception type in issue
        if exception_type_lower in issue_text:
            score += 0.4

        # Check for exception message similarity
        message_terms = self._extract_key_terms(traceback.exception_message)
        if message_terms:
            matches = sum(1 for term in message_terms if term.lower() in issue_text)
            term_ratio = matches / len(message_terms)
            score += 0.6 * term_ratio

        return min(score, 1.0)

    def _calculate_stack_score(
        self,
        traceback: ParsedTraceback,
        issue: Issue,
    ) -> float:
        """Calculate stack trace similarity score.

        Compares file names and function names from traceback with issue content.

        Args:
            traceback: Parsed traceback
            issue: Issue to compare against

        Returns:
            Score from 0.0 to 1.0
        """
        if not traceback.project_frames:
            return 0.0

        score = 0.0
        issue_text = f"{issue.title} {issue.body}".lower()

        # Check for file names
        file_matches = 0
        func_matches = 0

        for frame in traceback.project_frames:
            # Extract just the file name (not full path)
            file_name = frame.file_path.split("/")[-1].lower()
            if file_name in issue_text:
                file_matches += 1

            # Check function name
            if frame.function_name and frame.function_name.lower() in issue_text:
                func_matches += 1

        total_frames = len(traceback.project_frames)
        if total_frames > 0:
            file_score = file_matches / total_frames
            func_score = func_matches / total_frames
            score = file_score * 0.4 + func_score * 0.6

        return min(score, 1.0)

    async def calculate_semantic_similarity(
        self,
        traceback: ParsedTraceback,
        issues: list[Issue],
    ) -> list[tuple[Issue, float]]:
        """Calculate semantic similarity using LLM.

        This method uses the LLM to determine semantic similarity
        between the traceback and existing issues.

        Args:
            traceback: Parsed traceback
            issues: Issues to compare against

        Returns:
            List of (issue, similarity_score) tuples sorted by score descending
        """
        if not issues:
            return []

        try:
            # Use the LLM's built-in similarity calculation
            similarities = await self._llm.calculate_similarity(traceback, issues)
            return similarities
        except Exception as e:
            log.warning(
                "semantic_similarity_failed",
                error=str(e),
                fallback="using_basic_scoring",
            )
            # Fall back to basic scoring
            return [(issue, 0.0) for issue in issues]

    def set_strategy_weight(self, strategy_name: str, weight: float) -> None:
        """Set the weight for a matching strategy.

        Args:
            strategy_name: Name of the strategy ("exact", "stack", "semantic")
            weight: Weight value (will be normalized)

        Raises:
            ValueError: If strategy name is invalid
        """
        if strategy_name not in self._strategies:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        if weight < 0:
            raise ValueError("Weight cannot be negative")

        self._strategies[strategy_name].weight = weight
        log.info("strategy_weight_updated", strategy=strategy_name, weight=weight)

    def enable_strategy(self, strategy_name: str, enabled: bool = True) -> None:
        """Enable or disable a matching strategy.

        Args:
            strategy_name: Name of the strategy
            enabled: Whether to enable the strategy

        Raises:
            ValueError: If strategy name is invalid
        """
        if strategy_name not in self._strategies:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        self._strategies[strategy_name].enabled = enabled
        log.info("strategy_toggled", strategy=strategy_name, enabled=enabled)
