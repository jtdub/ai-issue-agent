"""Data models for error analysis."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CodeContext:
    """Code snippet with surrounding context."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    highlight_line: int | None = None  # Line to emphasize (error location)

    @property
    def line_count(self) -> int:
        """Number of lines in this code context."""
        return self.end_line - self.start_line + 1


@dataclass(frozen=True)
class SuggestedFix:
    """A suggested code fix."""

    description: str
    file_path: str
    original_code: str
    fixed_code: str
    confidence: float  # 0.0 to 1.0


@dataclass(frozen=True)
class ErrorAnalysis:
    """LLM analysis of an error."""

    root_cause: str
    explanation: str
    suggested_fixes: tuple[SuggestedFix, ...]
    related_documentation: tuple[str, ...]  # Links to relevant docs
    severity: str  # "low", "medium", "high", "critical"
    confidence: float  # Overall confidence in analysis
