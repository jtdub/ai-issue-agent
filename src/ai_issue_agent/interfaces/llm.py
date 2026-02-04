"""Abstract interface for LLM integrations."""

from typing import Protocol

from ..models.analysis import CodeContext, ErrorAnalysis
from ..models.issue import Issue
from ..models.traceback import ParsedTraceback


class LLMProvider(Protocol):
    """Abstract interface for LLM integrations.

    This protocol defines the contract that all LLM provider adapters
    (OpenAI, Anthropic, Ollama, etc.) must implement.
    """

    async def analyze_error(
        self,
        traceback: ParsedTraceback,
        code_context: list[CodeContext],
        additional_context: str | None = None,
    ) -> ErrorAnalysis:
        """
        Analyze an error traceback with surrounding code context.

        Security: The traceback MUST be redacted using SecretRedactor
        before being passed to this method.

        Args:
            traceback: Parsed traceback information (must be redacted)
            code_context: Relevant code snippets from referenced files
            additional_context: Optional additional information (e.g., README)

        Returns:
            Analysis including root cause and suggested fixes

        Raises:
            LLMAnalysisError: If analysis fails
            RateLimitError: If rate limit exceeded
            TimeoutError: If request times out
            ValidationError: If LLM output doesn't match expected schema
        """
        ...

    async def generate_issue_body(
        self,
        traceback: ParsedTraceback,
        analysis: ErrorAnalysis,
        code_context: list[CodeContext],
    ) -> str:
        """
        Generate a well-formatted issue body in Markdown.

        Security: The issue body MUST be redacted before creating
        a GitHub issue.

        Args:
            traceback: Original traceback data (must be redacted)
            analysis: LLM analysis results
            code_context: Code snippets for reference

        Returns:
            Markdown-formatted issue body

        Raises:
            LLMAnalysisError: If generation fails
            RateLimitError: If rate limit exceeded
        """
        ...

    async def generate_issue_title(
        self,
        traceback: ParsedTraceback,
        analysis: ErrorAnalysis,
    ) -> str:
        """
        Generate a concise, descriptive issue title.

        Args:
            traceback: Parsed traceback (must be redacted)
            analysis: Error analysis

        Returns:
            Issue title (recommended max ~80 characters)

        Raises:
            LLMAnalysisError: If generation fails
            RateLimitError: If rate limit exceeded
        """
        ...

    async def calculate_similarity(
        self,
        traceback: ParsedTraceback,
        existing_issues: list[Issue],
    ) -> list[tuple[Issue, float]]:
        """
        Calculate similarity between a traceback and existing issues.

        Used to determine if an issue already exists for this error.

        Args:
            traceback: Parsed traceback to match (must be redacted)
            existing_issues: Candidate issues to compare against

        Returns:
            List of (issue, similarity_score) tuples, sorted by score descending.
            Similarity scores range from 0.0 (no match) to 1.0 (exact match).

        Raises:
            LLMAnalysisError: If similarity calculation fails
            RateLimitError: If rate limit exceeded
        """
        ...

    @property
    def model_name(self) -> str:
        """
        Return the model identifier being used.

        Examples:
            - "gpt-4-turbo-preview"
            - "claude-3-sonnet-20240229"
            - "llama2:70b"
        """
        ...

    @property
    def max_context_tokens(self) -> int:
        """
        Return the maximum context window size in tokens.

        This is used to determine how much code context can be
        included in a single analysis request.
        """
        ...
