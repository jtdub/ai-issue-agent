"""Tests for TracebackParser functionality."""

import pytest

from ai_issue_agent.core.traceback_parser import TracebackParser
from ai_issue_agent.utils.async_helpers import TracebackParseError


@pytest.fixture
def parser() -> TracebackParser:
    """Create a TracebackParser instance."""
    return TracebackParser()


@pytest.fixture
def simple_traceback() -> str:
    """Return a simple traceback."""
    return """Traceback (most recent call last):
  File "/home/user/project/src/app/main.py", line 10, in main
    result = process_data(data)
  File "/home/user/project/src/app/processor.py", line 25, in process_data
    return parse_value(item)
  File "/home/user/project/src/app/utils.py", line 42, in parse_value
    raise ValueError("Invalid value")
ValueError: Invalid value
"""


@pytest.fixture
def chained_traceback() -> str:
    """Return a chained exception traceback."""
    return """Traceback (most recent call last):
  File "/home/user/project/src/app/main.py", line 10, in main
    result = fetch_data(url)
  File "/home/user/project/src/app/network.py", line 30, in fetch_data
    response = requests.get(url)
ConnectionError: Failed to connect to server

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/user/project/src/app/api.py", line 15, in get_resource
    data = load_from_network(url)
  File "/home/user/project/src/app/loader.py", line 20, in load_from_network
    raise DataLoadError("Failed to load data") from e
DataLoadError: Failed to load data
"""


@pytest.fixture
def syntax_error_traceback() -> str:
    """Return a syntax error traceback."""
    return """  File "/home/user/project/src/app/broken.py", line 5
    def broken_func(
                   ^
SyntaxError: unexpected EOF while parsing
"""


@pytest.fixture
def traceback_in_code_block() -> str:
    """Return a traceback inside a code block."""
    return """Here's the error I'm getting:

```python
Traceback (most recent call last):
  File "test.py", line 1, in <module>
    raise ValueError("test error")
ValueError: test error
```

Can you help?
"""


class TestTracebackParserContains:
    """Tests for contains_traceback method."""

    def test_contains_simple_traceback(
        self,
        parser: TracebackParser,
        simple_traceback: str,
    ) -> None:
        """Test detection of simple traceback."""
        assert parser.contains_traceback(simple_traceback) is True

    def test_contains_chained_traceback(
        self,
        parser: TracebackParser,
        chained_traceback: str,
    ) -> None:
        """Test detection of chained exception traceback."""
        assert parser.contains_traceback(chained_traceback) is True

    def test_contains_syntax_error(
        self,
        parser: TracebackParser,
        syntax_error_traceback: str,
    ) -> None:
        """Test detection of syntax error traceback."""
        assert parser.contains_traceback(syntax_error_traceback) is True

    def test_contains_code_block_traceback(
        self,
        parser: TracebackParser,
        traceback_in_code_block: str,
    ) -> None:
        """Test detection of traceback in code block."""
        assert parser.contains_traceback(traceback_in_code_block) is True

    def test_no_traceback_in_normal_text(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test that normal text returns False."""
        text = "This is just a normal message about fixing a bug."
        assert parser.contains_traceback(text) is False

    def test_no_traceback_empty_text(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test that empty text returns False."""
        assert parser.contains_traceback("") is False

    def test_partial_traceback_header(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test that partial traceback patterns don't match."""
        # Just mentioning "Traceback" shouldn't match
        text = "I saw a Traceback error yesterday"
        assert parser.contains_traceback(text) is False


class TestTracebackParserParse:
    """Tests for parse method."""

    def test_parse_simple_traceback(
        self,
        parser: TracebackParser,
        simple_traceback: str,
    ) -> None:
        """Test parsing a simple traceback."""
        result = parser.parse(simple_traceback)

        assert result.exception_type == "ValueError"
        assert result.exception_message == "Invalid value"
        assert result.is_chained is False
        assert result.cause is None

    def test_parse_extracts_frames(
        self,
        parser: TracebackParser,
        simple_traceback: str,
    ) -> None:
        """Test that frames are correctly extracted."""
        result = parser.parse(simple_traceback)

        assert len(result.frames) == 3

        # Check first frame
        first_frame = result.frames[0]
        assert "main.py" in first_frame.file_path
        assert first_frame.line_number == 10
        assert first_frame.function_name == "main"
        assert "process_data" in (first_frame.code_line or "")

        # Check last frame (innermost)
        last_frame = result.frames[-1]
        assert "utils.py" in last_frame.file_path
        assert last_frame.line_number == 42
        assert last_frame.function_name == "parse_value"

    def test_parse_chained_traceback(
        self,
        parser: TracebackParser,
        chained_traceback: str,
    ) -> None:
        """Test parsing a chained exception traceback."""
        result = parser.parse(chained_traceback)

        assert result.is_chained is True
        assert result.cause is not None
        assert result.exception_type == "DataLoadError"
        assert result.cause.exception_type == "ConnectionError"

    def test_parse_syntax_error(
        self,
        parser: TracebackParser,
        syntax_error_traceback: str,
    ) -> None:
        """Test parsing a syntax error traceback."""
        result = parser.parse(syntax_error_traceback)

        assert result.exception_type == "SyntaxError"
        assert "unexpected EOF" in result.exception_message
        assert len(result.frames) == 1
        assert result.frames[0].file_path == "/home/user/project/src/app/broken.py"
        assert result.frames[0].line_number == 5

    def test_parse_traceback_in_code_block(
        self,
        parser: TracebackParser,
        traceback_in_code_block: str,
    ) -> None:
        """Test parsing traceback from code block."""
        result = parser.parse(traceback_in_code_block)

        assert result.exception_type == "ValueError"
        assert result.exception_message == "test error"

    def test_parse_exception_no_message(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test parsing exception with no message."""
        traceback_text = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
    raise KeyboardInterrupt
KeyboardInterrupt
"""
        result = parser.parse(traceback_text)

        assert result.exception_type == "KeyboardInterrupt"
        assert result.exception_message == ""

    def test_parse_empty_text_raises(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test that empty text raises TracebackParseError."""
        with pytest.raises(TracebackParseError) as exc_info:
            parser.parse("")

        assert "Empty text" in str(exc_info.value)

    def test_parse_no_traceback_raises(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test that text without traceback raises TracebackParseError."""
        with pytest.raises(TracebackParseError):
            parser.parse("Just some normal text")

    def test_parse_preserves_raw_text(
        self,
        parser: TracebackParser,
        simple_traceback: str,
    ) -> None:
        """Test that raw_text is preserved."""
        result = parser.parse(simple_traceback)

        assert result.raw_text == simple_traceback


class TestTracebackParserExtractAll:
    """Tests for extract_all method."""

    def test_extract_all_single_traceback(
        self,
        parser: TracebackParser,
        simple_traceback: str,
    ) -> None:
        """Test extract_all with single traceback."""
        results = parser.extract_all(simple_traceback)

        assert len(results) == 1
        assert results[0].exception_type == "ValueError"

    def test_extract_all_chained_tracebacks(
        self,
        parser: TracebackParser,
        chained_traceback: str,
    ) -> None:
        """Test extracting all tracebacks from chained exception."""
        results = parser.extract_all(chained_traceback)

        # Should find both the original and the chained exception
        assert len(results) >= 2
        exception_types = [r.exception_type for r in results]
        assert "ConnectionError" in exception_types
        assert "DataLoadError" in exception_types

    def test_extract_all_no_tracebacks(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test extract_all with no tracebacks."""
        results = parser.extract_all("No tracebacks here")
        assert results == []


class TestStackFrameProperties:
    """Tests for StackFrame properties."""

    def test_is_stdlib_lib_path(self) -> None:
        """Test is_stdlib with library path."""
        from ai_issue_agent.models.traceback import StackFrame

        frame = StackFrame(
            file_path="/usr/lib/python3.11/json/__init__.py",
            line_number=100,
            function_name="loads",
        )
        assert frame.is_stdlib is True

    def test_is_stdlib_frozen(self) -> None:
        """Test is_stdlib with frozen module."""
        from ai_issue_agent.models.traceback import StackFrame

        frame = StackFrame(
            file_path="<frozen importlib._bootstrap>",
            line_number=100,
            function_name="_find_and_load",
        )
        assert frame.is_stdlib is True

    def test_is_stdlib_user_code(self) -> None:
        """Test is_stdlib with user code."""
        from ai_issue_agent.models.traceback import StackFrame

        frame = StackFrame(
            file_path="/home/user/project/src/app/main.py",
            line_number=10,
            function_name="main",
        )
        assert frame.is_stdlib is False

    def test_is_site_packages(self) -> None:
        """Test is_site_packages with installed package."""
        from ai_issue_agent.models.traceback import StackFrame

        frame = StackFrame(
            file_path="/home/user/.venv/lib/python3.11/site-packages/requests/api.py",
            line_number=50,
            function_name="get",
        )
        assert frame.is_site_packages is True

    def test_is_not_site_packages(self) -> None:
        """Test is_site_packages with user code."""
        from ai_issue_agent.models.traceback import StackFrame

        frame = StackFrame(
            file_path="/home/user/project/src/app/main.py",
            line_number=10,
            function_name="main",
        )
        assert frame.is_site_packages is False


class TestParsedTracebackProperties:
    """Tests for ParsedTraceback properties."""

    def test_innermost_frame(
        self,
        parser: TracebackParser,
        simple_traceback: str,
    ) -> None:
        """Test innermost_frame property."""
        result = parser.parse(simple_traceback)

        innermost = result.innermost_frame
        assert "utils.py" in innermost.file_path
        assert innermost.line_number == 42

    def test_innermost_frame_no_frames_raises(self) -> None:
        """Test innermost_frame raises when no frames."""
        from ai_issue_agent.models.traceback import ParsedTraceback

        tb = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=(),
            raw_text="test",
            is_chained=False,
            cause=None,
        )

        with pytest.raises(ValueError):
            _ = tb.innermost_frame

    def test_project_frames_filters_stdlib(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test project_frames filters out stdlib."""
        traceback_text = """Traceback (most recent call last):
  File "/usr/lib/python3.11/json/__init__.py", line 100, in loads
    return _default_decoder.decode(s)
  File "/home/user/project/src/app/main.py", line 10, in main
    data = json.loads(raw)
ValueError: Invalid JSON
"""
        result = parser.parse(traceback_text)
        project_frames = result.project_frames

        # Should only have user code frame
        assert len(project_frames) == 1
        assert "main.py" in project_frames[0].file_path

    def test_signature(
        self,
        parser: TracebackParser,
        simple_traceback: str,
    ) -> None:
        """Test signature property."""
        result = parser.parse(simple_traceback)

        assert result.signature == "ValueError: Invalid value"


class TestEdgeCases:
    """Tests for edge cases and special formats."""

    def test_multiline_exception_message(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test parsing exception with multiline message."""
        traceback_text = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
    raise AssertionError("Line 1")
AssertionError: Line 1
"""
        result = parser.parse(traceback_text)

        assert result.exception_type == "AssertionError"
        assert "Line 1" in result.exception_message

    def test_nested_module_exception(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test parsing exception from nested module."""
        traceback_text = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
    import foo
foo.bar.BazError: Something went wrong
"""
        result = parser.parse(traceback_text)

        assert result.exception_type == "foo.bar.BazError"

    def test_lambda_in_traceback(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test parsing traceback with lambda function."""
        traceback_text = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
    f = lambda x: x / 0
  File "test.py", line 1, in <lambda>
    f = lambda x: x / 0
ZeroDivisionError: division by zero
"""
        result = parser.parse(traceback_text)

        assert result.exception_type == "ZeroDivisionError"
        assert any("<lambda>" in f.function_name for f in result.frames)

    def test_windows_paths(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test parsing traceback with Windows-style paths."""
        # Note: Python tracebacks use forward slashes even on Windows in File lines
        traceback_text = """Traceback (most recent call last):
  File "C:/Users/user/project/main.py", line 10, in main
    run()
RuntimeError: Failed
"""
        result = parser.parse(traceback_text)

        assert "C:/Users/user/project/main.py" in result.frames[0].file_path

    def test_indentation_error(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test parsing IndentationError."""
        traceback_text = """  File "test.py", line 5
    def foo():
    ^
IndentationError: expected an indented block
"""
        result = parser.parse(traceback_text)

        assert result.exception_type == "IndentationError"

    def test_tab_error(
        self,
        parser: TracebackParser,
    ) -> None:
        """Test parsing TabError."""
        traceback_text = (
            '  File "test.py", line 5\n'
            "    \tx = 1\n"
            "       ^\n"
            "TabError: inconsistent use of tabs and spaces in indentation\n"
        )
        result = parser.parse(traceback_text)

        assert result.exception_type == "TabError"
