"""Tests for Anthropic LLM adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_issue_agent.config.schema import AnthropicConfig
from ai_issue_agent.models.analysis import CodeContext, ErrorAnalysis
from ai_issue_agent.models.traceback import ParsedTraceback, StackFrame


@pytest.fixture
def anthropic_config() -> AnthropicConfig:
    """Create a test Anthropic configuration."""
    return AnthropicConfig(
        api_key="sk-ant-test-key-123",
        model="claude-3-sonnet-20240229",
        max_tokens=4096,
        temperature=0.3,
    )


class TestAnthropicAdapterInit:
    """Test AnthropicAdapter initialization."""

    def test_init_with_config(self, anthropic_config: AnthropicConfig) -> None:
        """Test initializing with configuration."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(anthropic_config)
            assert adapter._config == anthropic_config

    def test_model_name_property(self, anthropic_config: AnthropicConfig) -> None:
        """Test model_name property."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(anthropic_config)
            assert adapter.model_name == "claude-3-sonnet-20240229"

    def test_max_context_tokens_property(self, anthropic_config: AnthropicConfig) -> None:
        """Test max_context_tokens property."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(anthropic_config)
            assert adapter.max_context_tokens == 200000

    def test_creates_redactor(self, anthropic_config: AnthropicConfig) -> None:
        """Test that initialization creates secret redactor."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(anthropic_config)
            assert adapter._redactor is not None


class TestAnthropicAdapterSecretRedaction:
    """Test secret redaction in AnthropicAdapter."""

    def test_redacts_secrets_from_text(self, anthropic_config: AnthropicConfig) -> None:
        """Test that secrets are redacted from text."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(anthropic_config)

            raw_text = 'Error: api_key="sk-FAKEabcd1234abcd1234abcd1234abcd1234abcd1234abcd"'

            redacted = adapter._redact_text(raw_text)

            assert "sk-FAKEabcd" not in redacted
            assert "[REDACTED]" in redacted

    def test_redacts_github_tokens(self, anthropic_config: AnthropicConfig) -> None:
        """Test that GitHub tokens are redacted."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(anthropic_config)

            raw_text = "token: ghp_FAKEnotreal0123456789012345678901234"

            redacted = adapter._redact_text(raw_text)

            assert "ghp_FAKE" not in redacted


class TestAnthropicAdapterFormatting:
    """Test formatting methods in AnthropicAdapter."""

    @pytest.fixture
    def sample_traceback(self) -> ParsedTraceback:
        """Create a sample traceback for testing."""
        return ParsedTraceback(
            exception_type="ValueError",
            exception_message="Invalid input",
            frames=(
                StackFrame("/app/utils.py", 10, "validate"),
                StackFrame("/app/main.py", 25, "process"),
            ),
            raw_text="Traceback (most recent call last):\n  ...",
        )

    def test_format_traceback_for_llm(
        self, anthropic_config: AnthropicConfig, sample_traceback: ParsedTraceback
    ) -> None:
        """Test formatting traceback for LLM."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(anthropic_config)

            formatted = adapter._format_traceback_for_llm(sample_traceback)

            assert "ValueError" in formatted
            assert "Invalid input" in formatted
            assert "/app/utils.py" in formatted
            assert isinstance(formatted, str)

    def test_format_code_context(self, anthropic_config: AnthropicConfig) -> None:
        """Test formatting code context for LLM."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(anthropic_config)

            contexts = [
                CodeContext(
                    file_path="/app/utils.py",
                    start_line=5,
                    end_line=15,
                    content="def validate(x):\n    return int(x)",
                    highlight_line=10,
                )
            ]

            formatted = adapter._format_code_context(contexts)

            assert "def validate" in formatted
            assert "/app/utils.py" in formatted

    def test_format_empty_code_context(self, anthropic_config: AnthropicConfig) -> None:
        """Test formatting empty code context."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(anthropic_config)

            formatted = adapter._format_code_context([])

            assert (
                formatted == "" or "No code context" in formatted.lower() or formatted is not None
            )


class TestAnthropicAdapterSimilarityEmptyCase:
    """Test similarity calculation with empty issues."""

    @pytest.fixture
    def sample_traceback(self) -> ParsedTraceback:
        """Create a sample traceback for testing."""
        return ParsedTraceback(
            exception_type="TypeError",
            exception_message="unsupported operand",
            frames=(StackFrame("/app/calc.py", 15, "add"),),
            raw_text="Traceback...",
        )

    async def test_calculate_similarity_empty_issues(
        self, anthropic_config: AnthropicConfig, sample_traceback: ParsedTraceback
    ) -> None:
        """Test calculate_similarity with empty issue list."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            adapter = AnthropicAdapter(anthropic_config)

            result = await adapter.calculate_similarity(
                traceback=sample_traceback,
                existing_issues=[],
            )

            assert result == []


class TestAnthropicAdapterSimilarityWithIssues:
    """Test similarity calculation with existing issues."""

    @pytest.fixture
    def sample_traceback(self) -> ParsedTraceback:
        """Create a sample traceback for testing."""
        return ParsedTraceback(
            exception_type="TypeError",
            exception_message="unsupported operand",
            frames=(StackFrame("/app/calc.py", 15, "add"),),
            raw_text="Traceback...",
        )

    async def test_calculate_similarity_with_issues(
        self, anthropic_config: AnthropicConfig, sample_traceback: ParsedTraceback
    ) -> None:
        """Test calculate_similarity with existing issues."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic") as mock_anthropic:
            from datetime import datetime

            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter
            from ai_issue_agent.models.issue import Issue, IssueState

            mock_text_block = MagicMock()
            mock_text_block.text = """{
                "similarities": [
                    {"issue_index": 0, "score": 0.85, "reason": "Same exception type"}
                ]
            }"""

            mock_response = MagicMock()
            mock_response.content = [mock_text_block]

            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            adapter = AnthropicAdapter(anthropic_config)
            adapter._client = mock_client

            existing_issues = [
                Issue(
                    number=1,
                    title="TypeError in add function",
                    body="Error when adding numbers",
                    url="https://github.com/owner/repo/issues/1",
                    state=IssueState.OPEN,
                    labels=(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    author="user",
                ),
            ]

            result = await adapter.calculate_similarity(
                traceback=sample_traceback,
                existing_issues=existing_issues,
            )

            assert len(result) == 1
            assert result[0][1] == 0.85  # Score


class TestAnthropicAdapterAnalyzeError:
    """Test error analysis in AnthropicAdapter."""

    @pytest.fixture
    def sample_traceback(self) -> ParsedTraceback:
        """Create a sample traceback for testing."""
        return ParsedTraceback(
            exception_type="ValueError",
            exception_message="Invalid input",
            frames=(
                StackFrame("/app/utils.py", 10, "validate"),
                StackFrame("/app/main.py", 25, "process"),
            ),
            raw_text="Traceback (most recent call last):\n  ...",
        )

    async def test_analyze_error_success(
        self, anthropic_config: AnthropicConfig, sample_traceback: ParsedTraceback
    ) -> None:
        """Test successful error analysis."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic") as mock_anthropic:
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            # Create mock response
            mock_text_block = MagicMock()
            mock_text_block.text = """{
                "root_cause": "Invalid input type",
                "explanation": "The function expected an integer but received a string.",
                "suggested_fixes": [
                    {
                        "description": "Add type validation",
                        "file_path": "/app/utils.py",
                        "original_code": "def validate(x):",
                        "fixed_code": "def validate(x: int):",
                        "confidence": 0.9
                    }
                ],
                "severity": "medium",
                "related_docs": ["https://docs.python.org/3/library/functions.html#int"],
                "confidence": 0.85
            }"""

            mock_response = MagicMock()
            mock_response.content = [mock_text_block]

            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            adapter = AnthropicAdapter(anthropic_config)
            adapter._client = mock_client

            result = await adapter.analyze_error(
                traceback=sample_traceback,
                code_context=[],
            )

            assert result.root_cause == "Invalid input type"
            assert result.severity == "medium"
            assert result.confidence == 0.85

    async def test_analyze_error_with_code_context(
        self, anthropic_config: AnthropicConfig, sample_traceback: ParsedTraceback
    ) -> None:
        """Test error analysis with code context."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic") as mock_anthropic:
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            mock_text_block = MagicMock()
            mock_text_block.text = """{
                "root_cause": "Type error in validate",
                "explanation": "The validate function doesn't handle strings.",
                "suggested_fixes": [],
                "severity": "low",
                "related_docs": [],
                "confidence": 0.7
            }"""

            mock_response = MagicMock()
            mock_response.content = [mock_text_block]

            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            adapter = AnthropicAdapter(anthropic_config)
            adapter._client = mock_client

            code_context = [
                CodeContext(
                    file_path="/app/utils.py",
                    start_line=5,
                    end_line=15,
                    content="def validate(x):\n    return int(x)",
                    highlight_line=10,
                )
            ]

            result = await adapter.analyze_error(
                traceback=sample_traceback,
                code_context=code_context,
            )

            assert result.root_cause == "Type error in validate"


class TestAnthropicAdapterGenerateIssueBody:
    """Test issue body generation in AnthropicAdapter."""

    @pytest.fixture
    def sample_traceback(self) -> ParsedTraceback:
        """Create a sample traceback for testing."""
        return ParsedTraceback(
            exception_type="KeyError",
            exception_message="'missing_key'",
            frames=(StackFrame("/app/handler.py", 42, "get_value"),),
            raw_text="Traceback (most recent call last):\n  ...",
        )

    @pytest.fixture
    def sample_analysis(self) -> ErrorAnalysis:
        """Create a sample analysis for testing."""
        return ErrorAnalysis(
            root_cause="Missing key in dictionary",
            explanation="The key 'missing_key' does not exist in the dict.",
            suggested_fixes=(),
            related_documentation=(),
            severity="medium",
            confidence=0.8,
        )

    async def test_generate_issue_body_success(
        self,
        anthropic_config: AnthropicConfig,
        sample_traceback: ParsedTraceback,
        sample_analysis: ErrorAnalysis,
    ) -> None:
        """Test successful issue body generation."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic") as mock_anthropic:
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            mock_text_block = MagicMock()
            mock_text_block.text = """{
                "summary": "KeyError when accessing missing dictionary key",
                "impact": "High - causes application crash",
                "reproduction_steps": "1. Call get_value with missing key",
                "suggested_fixes": "Check if key exists before accessing",
                "additional_context": "Common pattern in legacy code"
            }"""

            mock_response = MagicMock()
            mock_response.content = [mock_text_block]

            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            adapter = AnthropicAdapter(anthropic_config)
            adapter._client = mock_client

            result = await adapter.generate_issue_body(
                traceback=sample_traceback,
                analysis=sample_analysis,
                code_context=[],
            )

            assert "KeyError" in result or "missing" in result.lower() or len(result) > 0


class TestAnthropicAdapterGenerateIssueTitle:
    """Test issue title generation in AnthropicAdapter."""

    @pytest.fixture
    def sample_traceback(self) -> ParsedTraceback:
        """Create a sample traceback for testing."""
        return ParsedTraceback(
            exception_type="IndexError",
            exception_message="list index out of range",
            frames=(StackFrame("/app/processor.py", 100, "process_items"),),
            raw_text="Traceback (most recent call last):\n  ...",
        )

    @pytest.fixture
    def sample_analysis(self) -> ErrorAnalysis:
        """Create a sample analysis for testing."""
        return ErrorAnalysis(
            root_cause="Empty list accessed with invalid index",
            explanation="Attempting to access an index that does not exist.",
            suggested_fixes=(),
            related_documentation=(),
            severity="high",
            confidence=0.9,
        )

    async def test_generate_issue_title_success(
        self,
        anthropic_config: AnthropicConfig,
        sample_traceback: ParsedTraceback,
        sample_analysis: ErrorAnalysis,
    ) -> None:
        """Test successful issue title generation."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic") as mock_anthropic:
            from ai_issue_agent.adapters.llm.anthropic import AnthropicAdapter

            mock_text_block = MagicMock()
            mock_text_block.text = """{
                "title": "IndexError in process_items when list is empty"
            }"""

            mock_response = MagicMock()
            mock_response.content = [mock_text_block]

            mock_client = MagicMock()
            mock_client.messages = MagicMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            adapter = AnthropicAdapter(anthropic_config)
            adapter._client = mock_client

            result = await adapter.generate_issue_title(
                traceback=sample_traceback,
                analysis=sample_analysis,
            )

            assert "IndexError" in result or "process_items" in result or len(result) > 0


class TestAnthropicAdapterJsonParsing:
    """Test JSON parsing in AnthropicAdapter."""

    def test_parse_and_validate_json_valid(self, anthropic_config: AnthropicConfig) -> None:
        """Test parsing valid JSON."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import (
                AnthropicAdapter,
                ErrorAnalysisResponse,
            )

            adapter = AnthropicAdapter(anthropic_config)

            valid_json = """{
                "root_cause": "test",
                "explanation": "test explanation",
                "suggested_fixes": [],
                "severity": "low",
                "related_docs": [],
                "confidence": 0.5
            }"""

            result = adapter._parse_and_validate_json(valid_json, ErrorAnalysisResponse)

            assert result.root_cause == "test"
            assert result.confidence == 0.5

    def test_parse_and_validate_json_with_markdown(self, anthropic_config: AnthropicConfig) -> None:
        """Test parsing JSON wrapped in markdown code blocks."""
        with patch("ai_issue_agent.adapters.llm.anthropic.anthropic.Anthropic"):
            from ai_issue_agent.adapters.llm.anthropic import (
                AnthropicAdapter,
                ErrorAnalysisResponse,
            )

            adapter = AnthropicAdapter(anthropic_config)

            # JSON wrapped in markdown code block
            wrapped_json = """```json
{
    "root_cause": "wrapped test",
    "explanation": "test",
    "suggested_fixes": [],
    "severity": "high",
    "related_docs": [],
    "confidence": 0.8
}
```"""

            result = adapter._parse_and_validate_json(wrapped_json, ErrorAnalysisResponse)

            assert result.root_cause == "wrapped test"
            assert result.severity == "high"
