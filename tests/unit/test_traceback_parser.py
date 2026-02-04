"""Unit tests for TracebackParser."""

import pytest

from ai_issue_agent.core.traceback_parser import TracebackParser
from ai_issue_agent.utils.async_helpers import TracebackParseError


class TestContainsTraceback:
    """Tests for contains_traceback method."""

    def test_detects_standard_traceback(self, sample_traceback: str) -> None:
        """Test detection of standard Python traceback."""
        parser = TracebackParser()
        assert parser.contains_traceback(sample_traceback) is True

    def test_detects_nested_traceback(self, nested_traceback: str) -> None:
        """Test detection of chained exception traceback."""
        parser = TracebackParser()
        assert parser.contains_traceback(nested_traceback) is True

    def test_detects_traceback_in_code_block(self, code_block_traceback: str) -> None:
        """Test detection of traceback in markdown code block."""
        parser = TracebackParser()
        assert parser.contains_traceback(code_block_traceback) is True

    def test_detects_syntax_error(self, syntax_error_traceback: str) -> None:
        """Test detection of SyntaxError traceback."""
        parser = TracebackParser()
        assert parser.contains_traceback(syntax_error_traceback) is True

    def test_returns_false_for_normal_text(self) -> None:
        """Test that normal text is not detected as traceback."""
        parser = TracebackParser()
        assert parser.contains_traceback("Hello, this is normal text.") is False

    def test_returns_false_for_empty_text(self) -> None:
        """Test that empty text returns False."""
        parser = TracebackParser()
        assert parser.contains_traceback("") is False

    def test_returns_false_for_none(self) -> None:
        """Test that None-like values return False."""
        parser = TracebackParser()
        assert parser.contains_traceback("") is False


class TestParseSimpleTraceback:
    """Tests for parsing standard tracebacks."""

    def test_parses_simple_traceback(self, sample_traceback: str) -> None:
        """Test parsing a simple ValueError traceback."""
        parser = TracebackParser()
        result = parser.parse(sample_traceback)

        assert result.exception_type == "ValueError"
        assert "invalid literal for int()" in result.exception_message
        assert len(result.frames) == 2

    def test_extracts_frames_correctly(self, sample_traceback: str) -> None:
        """Test that stack frames are extracted correctly."""
        parser = TracebackParser()
        result = parser.parse(sample_traceback)

        # First frame
        assert result.frames[0].file_path == "/app/src/main.py"
        assert result.frames[0].line_number == 42
        assert result.frames[0].function_name == "process_request"
        assert result.frames[0].code_line == "result = calculate_value(data)"

        # Second frame
        assert result.frames[1].file_path == "/app/src/calculator.py"
        assert result.frames[1].line_number == 15
        assert result.frames[1].function_name == "calculate_value"
        assert result.frames[1].code_line == "return int(value)"

    def test_innermost_frame_property(self, sample_traceback: str) -> None:
        """Test that innermost_frame returns the last frame."""
        parser = TracebackParser()
        result = parser.parse(sample_traceback)

        assert result.innermost_frame.file_path == "/app/src/calculator.py"
        assert result.innermost_frame.line_number == 15

    def test_signature_property(self, sample_traceback: str) -> None:
        """Test that signature returns type: message format."""
        parser = TracebackParser()
        result = parser.parse(sample_traceback)

        assert result.signature.startswith("ValueError:")

    def test_raw_text_preserved(self, sample_traceback: str) -> None:
        """Test that raw_text contains original traceback."""
        parser = TracebackParser()
        result = parser.parse(sample_traceback)

        assert "Traceback (most recent call last):" in result.raw_text


class TestParseChainedExceptions:
    """Tests for parsing chained exception tracebacks."""

    def test_parses_chained_exception(self, nested_traceback: str) -> None:
        """Test parsing a chained exception traceback."""
        parser = TracebackParser()
        result = parser.parse(nested_traceback)

        # The outermost exception should be returned
        assert result.exception_type == "ServiceUnavailableError"
        assert "User service unavailable" in result.exception_message

    def test_extracts_all_chained_tracebacks(self, nested_traceback: str) -> None:
        """Test extracting all tracebacks from chain."""
        parser = TracebackParser()
        results = parser.extract_all(nested_traceback)

        assert len(results) == 2

        # First (innermost) exception
        assert results[0].exception_type == "ConnectionError"
        assert "Failed to connect" in results[0].exception_message
        assert results[0].is_chained is False

        # Second (outermost) exception
        assert results[1].exception_type == "ServiceUnavailableError"
        assert results[1].is_chained is True
        assert results[1].cause is not None
        assert results[1].cause.exception_type == "ConnectionError"

    def test_chained_exception_has_cause_reference(self, nested_traceback: str) -> None:
        """Test that chained exceptions have correct cause references."""
        parser = TracebackParser()
        results = parser.extract_all(nested_traceback)

        # The second traceback should reference the first as its cause
        assert results[1].cause == results[0]


class TestParseSyntaxError:
    """Tests for parsing SyntaxError tracebacks."""

    def test_parses_syntax_error(self, syntax_error_traceback: str) -> None:
        """Test parsing a SyntaxError traceback."""
        parser = TracebackParser()
        result = parser.parse(syntax_error_traceback)

        assert result.exception_type == "SyntaxError"
        assert "invalid syntax" in result.exception_message

    def test_syntax_error_has_frame(self, syntax_error_traceback: str) -> None:
        """Test that SyntaxError traceback has a frame."""
        parser = TracebackParser()
        result = parser.parse(syntax_error_traceback)

        assert len(result.frames) >= 1
        assert result.frames[0].file_path == "/app/src/config.py"
        assert result.frames[0].line_number == 25


class TestParseMultilineMessage:
    """Tests for parsing tracebacks with multi-line messages."""

    def test_parses_multiline_message(self, multiline_msg_traceback: str) -> None:
        """Test parsing a traceback with multi-line exception message."""
        parser = TracebackParser()
        result = parser.parse(multiline_msg_traceback)

        assert result.exception_type == "ConfigurationError"
        assert "Invalid configuration detected" in result.exception_message


class TestParseCodeBlock:
    """Tests for parsing tracebacks in markdown code blocks."""

    def test_extracts_from_code_block(self, code_block_traceback: str) -> None:
        """Test extracting traceback from markdown code block."""
        parser = TracebackParser()
        result = parser.parse(code_block_traceback)

        assert result.exception_type == "UserNotFoundError"
        assert "User 12345 not found" in result.exception_message

    def test_code_block_frames_extracted(self, code_block_traceback: str) -> None:
        """Test that frames are extracted from code block traceback."""
        parser = TracebackParser()
        result = parser.parse(code_block_traceback)

        assert len(result.frames) == 3
        assert "endpoints.py" in result.frames[0].file_path


class TestParseTruncated:
    """Tests for parsing truncated tracebacks."""

    def test_parses_truncated_traceback(self, truncated_traceback: str) -> None:
        """Test parsing a truncated traceback missing header."""
        parser = TracebackParser()
        result = parser.parse(truncated_traceback)

        assert result.exception_type == "JSONDecodeError"
        assert "Expecting value" in result.exception_message

    def test_truncated_extracts_available_frames(self, truncated_traceback: str) -> None:
        """Test that available frames are extracted from truncated traceback."""
        parser = TracebackParser()
        result = parser.parse(truncated_traceback)

        assert len(result.frames) == 2
        assert "processor.py" in result.frames[0].file_path
        assert "transformer.py" in result.frames[1].file_path


class TestStackFrameProperties:
    """Tests for StackFrame properties."""

    def test_is_stdlib_detection(self, sample_traceback: str) -> None:
        """Test that stdlib frames are correctly identified."""
        parser = TracebackParser()
        result = parser.parse(sample_traceback)

        # Our test fixtures use /app/src paths which are not stdlib
        for frame in result.frames:
            assert frame.is_stdlib is False

    def test_is_site_packages_detection(self) -> None:
        """Test that site-packages frames are correctly identified."""
        tb = """Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/requests/api.py", line 59, in get
    return request("get", url)
  File "/app/src/main.py", line 10, in fetch
    return requests.get(url)
requests.exceptions.ConnectionError: Failed to connect
"""
        parser = TracebackParser()
        result = parser.parse(tb)

        assert result.frames[0].is_site_packages is True
        assert result.frames[1].is_site_packages is False

    def test_project_frames_property(self) -> None:
        """Test that project_frames filters out stdlib/site-packages."""
        tb = """Traceback (most recent call last):
  File "/usr/lib/python3.11/asyncio/runners.py", line 44, in run
    return loop.run_until_complete(main)
  File "/app/src/main.py", line 10, in main
    await process()
ValueError: test error
"""
        parser = TracebackParser()
        result = parser.parse(tb)

        project_frames = result.project_frames
        assert len(project_frames) == 1
        assert "main.py" in project_frames[0].file_path

    def test_normalized_path(self) -> None:
        """Test that normalized_path strips absolute prefixes."""
        tb = """Traceback (most recent call last):
  File "/home/user/projects/myapp/src/main.py", line 10, in main
    process()
ValueError: test error
"""
        parser = TracebackParser()
        result = parser.parse(tb)

        # Normalized path should be shorter and relative-looking
        normalized = result.frames[0].normalized_path
        assert not normalized.startswith("/home/")


class TestErrorHandling:
    """Tests for error handling."""

    def test_raises_on_empty_text(self) -> None:
        """Test that parsing empty text raises TracebackParseError."""
        parser = TracebackParser()
        with pytest.raises(TracebackParseError):
            parser.parse("")

    def test_raises_on_non_traceback_text(self) -> None:
        """Test that parsing non-traceback text raises TracebackParseError."""
        parser = TracebackParser()
        with pytest.raises(TracebackParseError):
            parser.parse("This is just regular text with no traceback.")

    def test_extract_all_returns_empty_for_no_traceback(self) -> None:
        """Test that extract_all returns empty list for non-traceback text."""
        parser = TracebackParser()
        results = parser.extract_all("No traceback here")
        assert results == []


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_handles_unicode_in_message(self) -> None:
        """Test handling of unicode characters in exception message."""
        tb = """Traceback (most recent call last):
  File "/app/src/main.py", line 10, in process
    raise ValueError("Invalid character: \u00e9\u00e8\u00ea")
ValueError: Invalid character: \u00e9\u00e8\u00ea
"""
        parser = TracebackParser()
        result = parser.parse(tb)

        assert result.exception_type == "ValueError"
        assert "\u00e9" in result.exception_message

    def test_handles_very_long_file_paths(self) -> None:
        """Test handling of very long file paths."""
        long_path = "/very/long/path/" + "subdir/" * 20 + "file.py"
        tb = f"""Traceback (most recent call last):
  File "{long_path}", line 10, in func
    raise ValueError("test")
ValueError: test
"""
        parser = TracebackParser()
        result = parser.parse(tb)

        assert result.frames[0].file_path == long_path

    def test_handles_special_characters_in_message(self) -> None:
        """Test handling of special characters in exception message."""
        tb = """Traceback (most recent call last):
  File "/app/src/main.py", line 10, in process
    raise ValueError("Error: <script>alert('xss')</script>")
ValueError: Error: <script>alert('xss')</script>
"""
        parser = TracebackParser()
        result = parser.parse(tb)

        assert "<script>" in result.exception_message

    def test_handles_exception_without_message(self) -> None:
        """Test handling of exception with no message."""
        tb = """Traceback (most recent call last):
  File "/app/src/main.py", line 10, in process
    raise RuntimeError()
RuntimeError
"""
        parser = TracebackParser()
        result = parser.parse(tb)

        assert result.exception_type == "RuntimeError"
        assert result.exception_message == ""
