"""Python traceback parser.

This module provides robust parsing of Python tracebacks from text,
supporting various formats including:
- Standard tracebacks
- Tracebacks in markdown code blocks
- SyntaxError format
- Multi-line exception messages
- Chained exceptions (raise ... from ...)
- Truncated tracebacks

See docs/ARCHITECTURE.md for design details.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from ..models.traceback import ParsedTraceback, StackFrame
from ..utils.async_helpers import TracebackParseError

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# Regex patterns for traceback parsing

# Standard traceback header
TRACEBACK_HEADER = re.compile(r"Traceback \(most recent call last\):")

# Frame line pattern: File "path", line N, in func_name
FRAME_PATTERN = re.compile(
    r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>\S+)\s*$',
    re.MULTILINE,
)

# Code line pattern (indented code following a frame)
CODE_LINE_PATTERN = re.compile(r"^    (.+)$", re.MULTILINE)

# Exception line pattern: ExceptionType: message or just ExceptionType
EXCEPTION_PATTERN = re.compile(
    r"^(?P<type>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)(?:: (?P<message>.+))?$",
    re.MULTILINE,
)

# Chained exception separator patterns
CAUSE_PATTERN = re.compile(
    r"\n\nThe above exception was the direct cause of the following exception:\n\n",
    re.MULTILINE,
)
CONTEXT_PATTERN = re.compile(
    r"\n\nDuring handling of the above exception, another exception occurred:\n\n",
    re.MULTILINE,
)

# SyntaxError specific patterns
SYNTAX_ERROR_HEADER = re.compile(
    r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+)\s*$',
    re.MULTILINE,
)
SYNTAX_ERROR_CARET = re.compile(r"^\s*\^\s*$", re.MULTILINE)

# Markdown code block pattern
CODE_BLOCK_PATTERN = re.compile(
    r"```(?:python|py)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class _RawFrame:
    """Intermediate representation of a parsed frame."""

    file_path: str
    line_number: int
    function_name: str
    code_line: str | None = None


class TracebackParser:
    """Parser for Python tracebacks.

    This class provides methods to detect and parse Python tracebacks
    from text, supporting various formats and edge cases.

    Example:
        parser = TracebackParser()
        if parser.contains_traceback(text):
            traceback = parser.parse(text)
            print(f"Exception: {traceback.exception_type}")
    """

    def __init__(self) -> None:
        """Initialize the TracebackParser."""
        pass

    def contains_traceback(self, text: str) -> bool:
        """Check if text contains a Python traceback.

        Args:
            text: The text to check.

        Returns:
            True if a Python traceback is detected, False otherwise.
        """
        if not text:
            return False

        # First, try to extract from code blocks
        extracted = self._extract_from_code_blocks(text)
        text_to_check = extracted if extracted else text

        # Check for standard traceback header
        if TRACEBACK_HEADER.search(text_to_check):
            return True

        # Check for SyntaxError format (doesn't have standard header)
        return "SyntaxError:" in text_to_check

    def parse(self, text: str) -> ParsedTraceback:
        """Parse a Python traceback from text.

        This method extracts the first complete traceback from the text.
        For multiple/chained tracebacks, use extract_all().

        Args:
            text: The text containing a traceback.

        Returns:
            ParsedTraceback with exception info and stack frames.

        Raises:
            TracebackParseError: If no valid traceback is found.
        """
        if not text:
            raise TracebackParseError("Empty text provided")

        # Try to extract from code blocks first
        extracted = self._extract_from_code_blocks(text)
        text_to_parse = extracted if extracted else text

        # Check for chained exceptions
        all_tracebacks = self.extract_all(text_to_parse)
        if all_tracebacks:
            return all_tracebacks[-1]  # Return the final (outermost) exception

        raise TracebackParseError("No valid traceback found in text")

    def extract_all(self, text: str) -> list[ParsedTraceback]:
        """Extract all tracebacks from text (for chained exceptions).

        Args:
            text: The text containing one or more tracebacks.

        Returns:
            List of ParsedTraceback objects. For chained exceptions,
            the list is ordered from innermost (cause) to outermost.
            Empty list if no tracebacks found.
        """
        if not text:
            return []

        # Try to extract from code blocks first
        extracted = self._extract_from_code_blocks(text)
        text_to_parse = extracted if extracted else text

        # Split by chained exception patterns
        parts = self._split_chained_tracebacks(text_to_parse)

        tracebacks: list[ParsedTraceback] = []
        for i, part in enumerate(parts):
            try:
                tb = self._parse_single_traceback(part, is_chained=(i > 0))
                if tb:
                    tracebacks.append(tb)
            except TracebackParseError:
                # Skip parts that don't parse as valid tracebacks
                continue

        # Link chained exceptions
        if len(tracebacks) > 1:
            linked_tracebacks: list[ParsedTraceback] = []
            for i, tb in enumerate(tracebacks):
                if i > 0:
                    # This traceback was caused by the previous one
                    tb = ParsedTraceback(
                        exception_type=tb.exception_type,
                        exception_message=tb.exception_message,
                        frames=tb.frames,
                        raw_text=tb.raw_text,
                        is_chained=True,
                        cause=tracebacks[i - 1],
                    )
                linked_tracebacks.append(tb)
            return linked_tracebacks

        return tracebacks

    def _extract_from_code_blocks(self, text: str) -> str | None:
        """Extract traceback from markdown code blocks.

        Args:
            text: Text that may contain markdown code blocks.

        Returns:
            Extracted content from code blocks, or None if no code blocks.
        """
        matches: list[str] = CODE_BLOCK_PATTERN.findall(text)
        if matches:
            # Combine all code blocks that might contain tracebacks
            for match in matches:
                if TRACEBACK_HEADER.search(match) or "Error:" in match:
                    return str(match).strip()
        return None

    def _split_chained_tracebacks(self, text: str) -> list[str]:
        """Split text containing chained exceptions.

        Args:
            text: Text that may contain chained exceptions.

        Returns:
            List of individual traceback text blocks.
        """
        # Split by cause pattern first
        parts = CAUSE_PATTERN.split(text)
        if len(parts) > 1:
            return parts

        # Try context pattern
        parts = CONTEXT_PATTERN.split(text)
        return parts

    def _parse_single_traceback(
        self, text: str, is_chained: bool = False
    ) -> ParsedTraceback | None:
        """Parse a single traceback (not chained).

        Args:
            text: Text containing a single traceback.
            is_chained: Whether this is part of a chain.

        Returns:
            ParsedTraceback or None if parsing fails.

        Raises:
            TracebackParseError: If the traceback format is invalid.
        """
        text = text.strip()
        if not text:
            return None

        # Check for SyntaxError (special format)
        if "SyntaxError:" in text:
            return self._parse_syntax_error(text, is_chained)

        # Must have traceback header for standard format
        if not TRACEBACK_HEADER.search(text):
            # Try to parse anyway if it looks like an exception
            exception_match = EXCEPTION_PATTERN.search(text)
            if exception_match:
                # Might be a truncated traceback
                return self._parse_truncated(text, is_chained)
            return None

        # Extract frames
        frames = self._extract_frames(text)

        # Extract exception info (last line usually)
        exception_type, exception_message = self._extract_exception(text)

        if not exception_type:
            raise TracebackParseError("Could not extract exception type")

        return ParsedTraceback(
            exception_type=exception_type,
            exception_message=exception_message,
            frames=tuple(frames),
            raw_text=text,
            is_chained=is_chained,
            cause=None,
        )

    def _extract_frames(self, text: str) -> list[StackFrame]:
        """Extract stack frames from traceback text.

        Args:
            text: Traceback text.

        Returns:
            List of StackFrame objects.
        """
        frames: list[StackFrame] = []
        lines = text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]
            frame_match = FRAME_PATTERN.match(line)

            if frame_match:
                file_path = frame_match.group("file")
                line_number = int(frame_match.group("line"))
                function_name = frame_match.group("func")

                # Check for code line on next line(s)
                code_line = None
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if next_line.startswith("    ") and not FRAME_PATTERN.match(next_line):
                        code_line = next_line.strip()
                        i += 1

                frames.append(
                    StackFrame(
                        file_path=file_path,
                        line_number=line_number,
                        function_name=function_name,
                        code_line=code_line,
                    )
                )
            i += 1

        return frames

    def _extract_exception(self, text: str) -> tuple[str, str]:
        """Extract exception type and message from traceback text.

        Args:
            text: Traceback text.

        Returns:
            Tuple of (exception_type, exception_message).
        """
        lines = text.strip().split("\n")

        # The exception line is typically the last line(s)
        # It may span multiple lines for multi-line messages
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()

            # Skip empty lines and code lines
            if not line or line.startswith("File ") or line.startswith("^"):
                continue

            # Check if this looks like an exception line
            exception_match = EXCEPTION_PATTERN.match(line)
            if exception_match:
                exception_type = exception_match.group("type")
                exception_message = exception_match.group("message") or ""

                # Check for multi-line message (subsequent indented lines)
                for j in range(i + 1, len(lines)):
                    next_line = lines[j]
                    # If it's indented and not a frame, it's part of the message
                    if (
                        next_line
                        and not next_line.startswith("Traceback")
                        and not FRAME_PATTERN.match(next_line)
                    ):
                        if next_line.startswith("  ") or next_line.startswith("\t"):
                            exception_message += "\n" + next_line.strip()
                        else:
                            break
                    else:
                        break

                return exception_type, exception_message.strip()

        return "", ""

    def _parse_syntax_error(self, text: str, is_chained: bool = False) -> ParsedTraceback:
        """Parse a SyntaxError traceback.

        SyntaxErrors have a different format:
          File "path", line N
            code_line
                ^
        SyntaxError: message

        Args:
            text: Text containing a SyntaxError traceback.
            is_chained: Whether this is part of a chain.

        Returns:
            ParsedTraceback for the syntax error.
        """
        frames: list[StackFrame] = []
        lines = text.split("\n")

        file_path = ""
        line_number = 0
        code_line = None

        for i, line in enumerate(lines):
            # Check for file/line header
            header_match = SYNTAX_ERROR_HEADER.match(line)
            if header_match:
                file_path = header_match.group("file")
                line_number = int(header_match.group("line"))

                # Next line should be the code
                next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if next_line and not next_line.startswith("^"):
                    code_line = next_line
                continue

        # If we found a file, create a frame
        if file_path:
            frames.append(
                StackFrame(
                    file_path=file_path,
                    line_number=line_number,
                    function_name="<module>",
                    code_line=code_line,
                )
            )

        # Extract exception type and message
        exception_type, exception_message = self._extract_exception(text)

        # Default to SyntaxError if not found
        if not exception_type:
            exception_type = "SyntaxError"
            # Try to find the message after SyntaxError:
            for line in lines:
                if "SyntaxError:" in line:
                    parts = line.split("SyntaxError:", 1)
                    if len(parts) > 1:
                        exception_message = parts[1].strip()
                    break

        return ParsedTraceback(
            exception_type=exception_type,
            exception_message=exception_message,
            frames=tuple(frames),
            raw_text=text,
            is_chained=is_chained,
            cause=None,
        )

    def _parse_truncated(self, text: str, is_chained: bool = False) -> ParsedTraceback | None:
        """Parse a truncated traceback (missing header or frames).

        Args:
            text: Text containing a truncated traceback.
            is_chained: Whether this is part of a chain.

        Returns:
            ParsedTraceback if we can extract useful info, None otherwise.
        """
        # Try to extract any frames we can find
        frames = self._extract_frames(text)

        # Extract exception info
        exception_type, exception_message = self._extract_exception(text)

        if not exception_type:
            return None

        return ParsedTraceback(
            exception_type=exception_type,
            exception_message=exception_message,
            frames=tuple(frames),
            raw_text=text,
            is_chained=is_chained,
            cause=None,
        )
