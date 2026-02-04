"""Tests for traceback data models."""

import pytest

from ai_issue_agent.models.traceback import ParsedTraceback, StackFrame


class TestStackFrame:
    """Test StackFrame dataclass."""

    def test_create_basic_frame(self) -> None:
        """Test creating a basic stack frame."""
        frame = StackFrame(
            file_path="/app/src/main.py",
            line_number=42,
            function_name="process_data",
            code_line="result = transform(data)",
        )

        assert frame.file_path == "/app/src/main.py"
        assert frame.line_number == 42
        assert frame.function_name == "process_data"
        assert frame.code_line == "result = transform(data)"

    def test_create_frame_without_code_line(self) -> None:
        """Test creating a frame without code line (optional)."""
        frame = StackFrame(
            file_path="/app/src/main.py",
            line_number=42,
            function_name="process_data",
        )

        assert frame.code_line is None

    def test_is_stdlib_detects_python_lib(self) -> None:
        """Test is_stdlib property identifies standard library frames."""
        frames = [
            StackFrame("/usr/lib/python3.11/asyncio/events.py", 1, "foo"),
            StackFrame("/usr/lib64/python3.11/json/__init__.py", 1, "foo"),
            StackFrame("C:\\lib\\python311\\os.py", 1, "foo"),
            StackFrame("<frozen importlib._bootstrap>", 1, "foo"),
            StackFrame("<built-in>", 1, "foo"),
        ]

        for frame in frames:
            assert frame.is_stdlib, f"Expected {frame.file_path} to be stdlib"

    def test_is_stdlib_false_for_project_code(self) -> None:
        """Test is_stdlib returns False for project code."""
        frame = StackFrame("/app/src/main.py", 1, "foo")
        assert not frame.is_stdlib

    def test_is_site_packages_detects_third_party(self) -> None:
        """Test is_site_packages identifies third-party packages."""
        frames = [
            StackFrame("/usr/lib/python3.11/site-packages/requests/api.py", 1, "foo"),
            StackFrame(
                "/home/user/.local/lib/python3.11/site-packages/django/core.py",
                1,
                "foo",
            ),
            StackFrame("/usr/lib/python3.11/dist-packages/pkg/mod.py", 1, "foo"),
        ]

        for frame in frames:
            assert frame.is_site_packages, f"Expected {frame.file_path} to be site-packages"

    def test_is_site_packages_false_for_project_code(self) -> None:
        """Test is_site_packages returns False for project code."""
        frame = StackFrame("/app/src/main.py", 1, "foo")
        assert not frame.is_site_packages

    def test_normalized_path_strips_prefixes(self) -> None:
        """Test normalized_path removes common absolute prefixes."""
        test_cases = [
            ("/usr/local/app/src/main.py", "app/src/main.py"),
            ("/home/user/project/src/app.py", "project/src/app.py"),
            ("/Users/alice/work/myapp/core.py", "work/myapp/core.py"),
            ("C:\\projects\\app\\main.py", "projects/app/main.py"),
            ("relative/path/file.py", "relative/path/file.py"),
        ]

        for original, expected in test_cases:
            frame = StackFrame(original, 1, "foo")
            assert frame.normalized_path == expected, (
                f"Expected {expected}, got {frame.normalized_path}"
            )

    def test_frozen_immutable(self) -> None:
        """Test that StackFrame is frozen (immutable)."""
        frame = StackFrame("/app/main.py", 1, "foo")

        with pytest.raises(AttributeError):
            frame.line_number = 99  # type: ignore


class TestParsedTraceback:
    """Test ParsedTraceback dataclass."""

    def test_create_simple_traceback(self) -> None:
        """Test creating a simple traceback."""
        frame1 = StackFrame("/app/main.py", 10, "main")
        frame2 = StackFrame("/app/utils.py", 42, "helper")

        tb = ParsedTraceback(
            exception_type="ValueError",
            exception_message="invalid literal for int(): 'abc'",
            frames=(frame1, frame2),
            raw_text="Traceback (most recent call last):\n...",
        )

        assert tb.exception_type == "ValueError"
        assert tb.exception_message == "invalid literal for int(): 'abc'"
        assert len(tb.frames) == 2
        assert tb.frames[0] == frame1
        assert tb.frames[1] == frame2
        assert not tb.is_chained
        assert tb.cause is None

    def test_create_chained_traceback(self) -> None:
        """Test creating a chained exception traceback."""
        frame1 = StackFrame("/app/main.py", 10, "main")
        cause_frame = StackFrame("/app/db.py", 20, "connect")

        cause = ParsedTraceback(
            exception_type="ConnectionError",
            exception_message="Database unavailable",
            frames=(cause_frame,),
            raw_text="...",
        )

        tb = ParsedTraceback(
            exception_type="RuntimeError",
            exception_message="Failed to process data",
            frames=(frame1,),
            raw_text="...",
            is_chained=True,
            cause=cause,
        )

        assert tb.is_chained
        assert tb.cause == cause
        assert tb.cause.exception_type == "ConnectionError"

    def test_innermost_frame_returns_last(self) -> None:
        """Test innermost_frame property returns the last frame."""
        frames = (
            StackFrame("/app/main.py", 10, "main"),
            StackFrame("/app/utils.py", 42, "helper"),
            StackFrame("/app/db.py", 100, "query"),
        )

        tb = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=frames,
            raw_text="...",
        )

        assert tb.innermost_frame == frames[2]
        assert tb.innermost_frame.file_path == "/app/db.py"

    def test_innermost_frame_raises_on_empty(self) -> None:
        """Test innermost_frame raises error if no frames."""
        tb = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=(),
            raw_text="...",
        )

        with pytest.raises(ValueError, match="Traceback has no frames"):
            _ = tb.innermost_frame

    def test_project_frames_filters_stdlib_and_site_packages(self) -> None:
        """Test project_frames filters out stdlib and third-party code."""
        frames = (
            StackFrame("/app/main.py", 10, "main"),  # project
            StackFrame("/usr/lib/python3.11/asyncio/events.py", 20, "run"),  # stdlib
            StackFrame("/app/utils.py", 30, "helper"),  # project
            StackFrame("/usr/lib/python3.11/site-packages/requests/api.py", 40, "get"),  # 3rd party
            StackFrame("/app/db.py", 50, "query"),  # project
        )

        tb = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=frames,
            raw_text="...",
        )

        project_frames = tb.project_frames
        assert len(project_frames) == 3
        assert project_frames[0].file_path == "/app/main.py"
        assert project_frames[1].file_path == "/app/utils.py"
        assert project_frames[2].file_path == "/app/db.py"

    def test_project_frames_empty_if_no_project_code(self) -> None:
        """Test project_frames returns empty tuple if all frames are stdlib."""
        frames = (
            StackFrame("/usr/lib/python3.11/asyncio/events.py", 20, "run"),
            StackFrame("/usr/lib/python3.11/site-packages/requests/api.py", 40, "get"),
        )

        tb = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=frames,
            raw_text="...",
        )

        assert len(tb.project_frames) == 0

    def test_signature_format(self) -> None:
        """Test signature property format for deduplication."""
        tb = ParsedTraceback(
            exception_type="ValueError",
            exception_message="invalid literal for int(): 'abc'",
            frames=(StackFrame("/app/main.py", 1, "foo"),),
            raw_text="...",
        )

        assert tb.signature == "ValueError: invalid literal for int(): 'abc'"

    def test_frames_must_be_tuple(self) -> None:
        """Test that frames is stored as tuple (immutable)."""
        tb = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=(StackFrame("/app/main.py", 1, "foo"),),
            raw_text="...",
        )

        assert isinstance(tb.frames, tuple)

    def test_frozen_immutable(self) -> None:
        """Test that ParsedTraceback is frozen (immutable)."""
        tb = ParsedTraceback(
            exception_type="ValueError",
            exception_message="test",
            frames=(StackFrame("/app/main.py", 1, "foo"),),
            raw_text="...",
        )

        with pytest.raises(AttributeError):
            tb.exception_type = "TypeError"  # type: ignore
