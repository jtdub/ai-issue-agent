"""Tests for analysis data models."""

import pytest

from ai_issue_agent.models.analysis import CodeContext, ErrorAnalysis, SuggestedFix


class TestCodeContext:
    """Test CodeContext dataclass."""

    def test_create_code_context(self):
        """Test creating a CodeContext."""
        code = """def process_data(data):
    result = transform(data)
    return result"""

        context = CodeContext(
            file_path="/app/src/processor.py",
            start_line=10,
            end_line=12,
            content=code,
            highlight_line=11,
        )

        assert context.file_path == "/app/src/processor.py"
        assert context.start_line == 10
        assert context.end_line == 12
        assert context.content == code
        assert context.highlight_line == 11

    def test_create_context_without_highlight(self):
        """Test creating context without highlight line."""
        context = CodeContext(
            file_path="/app/main.py",
            start_line=1,
            end_line=5,
            content="code here",
        )

        assert context.highlight_line is None

    def test_line_count_property(self):
        """Test line_count property calculation."""
        test_cases = [
            (1, 1, 1),  # Single line
            (1, 5, 5),  # Five lines
            (10, 20, 11),  # Eleven lines
            (100, 150, 51),  # 51 lines
        ]

        for start, end, expected_count in test_cases:
            context = CodeContext(
                file_path="test.py",
                start_line=start,
                end_line=end,
                content="",
            )
            assert (
                context.line_count == expected_count
            ), f"Expected {expected_count} for lines {start}-{end}"

    def test_frozen_immutable(self):
        """Test that CodeContext is frozen (immutable)."""
        context = CodeContext(
            file_path="test.py",
            start_line=1,
            end_line=5,
            content="code",
        )

        with pytest.raises(AttributeError):
            context.start_line = 10  # type: ignore


class TestSuggestedFix:
    """Test SuggestedFix dataclass."""

    def test_create_suggested_fix(self):
        """Test creating a SuggestedFix."""
        fix = SuggestedFix(
            description="Add type validation before conversion",
            file_path="/app/src/processor.py",
            original_code="result = int(value)",
            fixed_code="result = int(value) if value.isdigit() else 0",
            confidence=0.85,
        )

        assert fix.description == "Add type validation before conversion"
        assert fix.file_path == "/app/src/processor.py"
        assert "int(value)" in fix.original_code
        assert "isdigit()" in fix.fixed_code
        assert fix.confidence == 0.85

    def test_confidence_as_float(self):
        """Test confidence is stored as float."""
        fix = SuggestedFix(
            description="Test",
            file_path="test.py",
            original_code="old",
            fixed_code="new",
            confidence=0.9,
        )

        assert isinstance(fix.confidence, float)
        assert 0.0 <= fix.confidence <= 1.0

    def test_frozen_immutable(self):
        """Test that SuggestedFix is frozen (immutable)."""
        fix = SuggestedFix(
            description="Test",
            file_path="test.py",
            original_code="old",
            fixed_code="new",
            confidence=0.5,
        )

        with pytest.raises(AttributeError):
            fix.confidence = 0.9  # type: ignore


class TestErrorAnalysis:
    """Test ErrorAnalysis dataclass."""

    def test_create_error_analysis(self):
        """Test creating an ErrorAnalysis."""
        fix1 = SuggestedFix(
            description="Fix type error",
            file_path="main.py",
            original_code="x = int(s)",
            fixed_code="x = int(s) if s.isdigit() else 0",
            confidence=0.8,
        )

        fix2 = SuggestedFix(
            description="Add error handling",
            file_path="main.py",
            original_code="x = int(s)",
            fixed_code="try:\n    x = int(s)\nexcept ValueError:\n    x = 0",
            confidence=0.9,
        )

        analysis = ErrorAnalysis(
            root_cause="Attempting to convert non-numeric string to integer",
            explanation="The code calls int() on a string that may contain non-numeric characters, causing a ValueError.",
            suggested_fixes=(fix1, fix2),
            related_documentation=(
                "https://docs.python.org/3/library/functions.html#int",
                "https://docs.python.org/3/library/exceptions.html#ValueError",
            ),
            severity="medium",
            confidence=0.85,
        )

        assert "convert non-numeric string" in analysis.root_cause
        assert "ValueError" in analysis.explanation
        assert len(analysis.suggested_fixes) == 2
        assert analysis.suggested_fixes[0] == fix1
        assert analysis.suggested_fixes[1] == fix2
        assert len(analysis.related_documentation) == 2
        assert analysis.severity == "medium"
        assert analysis.confidence == 0.85

    def test_create_analysis_with_no_fixes(self):
        """Test creating analysis with no suggested fixes."""
        analysis = ErrorAnalysis(
            root_cause="Complex error",
            explanation="Unable to determine specific fix",
            suggested_fixes=(),
            related_documentation=(),
            severity="high",
            confidence=0.5,
        )

        assert len(analysis.suggested_fixes) == 0
        assert len(analysis.related_documentation) == 0

    def test_severity_values(self):
        """Test different severity levels."""
        severities = ["low", "medium", "high", "critical"]

        for severity in severities:
            analysis = ErrorAnalysis(
                root_cause="Test",
                explanation="Test",
                suggested_fixes=(),
                related_documentation=(),
                severity=severity,
                confidence=0.5,
            )
            assert analysis.severity == severity

    def test_suggested_fixes_is_tuple(self):
        """Test that suggested_fixes is a tuple (immutable)."""
        fix = SuggestedFix(
            description="Test",
            file_path="test.py",
            original_code="old",
            fixed_code="new",
            confidence=0.5,
        )

        analysis = ErrorAnalysis(
            root_cause="Test",
            explanation="Test",
            suggested_fixes=(fix,),
            related_documentation=(),
            severity="low",
            confidence=0.5,
        )

        assert isinstance(analysis.suggested_fixes, tuple)

    def test_related_documentation_is_tuple(self):
        """Test that related_documentation is a tuple."""
        analysis = ErrorAnalysis(
            root_cause="Test",
            explanation="Test",
            suggested_fixes=(),
            related_documentation=("https://example.com/doc1", "https://example.com/doc2"),
            severity="low",
            confidence=0.5,
        )

        assert isinstance(analysis.related_documentation, tuple)

    def test_frozen_immutable(self):
        """Test that ErrorAnalysis is frozen (immutable)."""
        analysis = ErrorAnalysis(
            root_cause="Test",
            explanation="Test",
            suggested_fixes=(),
            related_documentation=(),
            severity="low",
            confidence=0.5,
        )

        with pytest.raises(AttributeError):
            analysis.severity = "high"  # type: ignore
