"""Parser for Python tracebacks.

This module implements the TracebackParser class that detects and parses
Python tracebacks from text. It supports:
- Standard tracebacks
- Chained exceptions (raise ... from ...)
- SyntaxError tracebacks
- Tracebacks in code blocks (```)
- Multi-line exception messages

See docs/ARCHITECTURE.md for the canonical design.
"""

from __future__ import annotations

import re

import structlog

from ai_issue_agent.models.traceback import ParsedTraceback, StackFrame
from ai_issue_agent.utils.async_helpers import TracebackParseError

log = structlog.get_logger()


class TracebackParser:
    """Parser for Python tracebacks.

    Responsibilities:
    - Detect if text contains a Python traceback
    - Extract exception type, message, and stack frames
    - Handle various traceback formats (standard, chained, syntax errors)
    - Normalize file paths for matching

    Example:
        parser = TracebackParser()
        if parser.contains_traceback(text):
            traceback = parser.parse(text)
            print(f"Exception: {traceback.exception_type}")
    """

    # Regex patterns for traceback parsing
    TRACEBACK_HEADER = re.compile(r"Traceback \(most recent call last\):")
    FRAME_PATTERN = re.compile(
        r'^\s*File "([^"]+)", line (\d+)(?:, in (.+))?$',
        re.MULTILINE,
    )
    EXCEPTION_PATTERN = re.compile(
        r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*):\s*(.*)$",
        re.MULTILINE,
    )
    EXCEPTION_NO_MSG_PATTERN = re.compile(
        r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)$",
        re.MULTILINE,
    )
    CHAINED_PATTERN = re.compile(
        r"^(?:The above exception was the direct cause of the following exception:|"
        r"During handling of the above exception, another exception occurred:)$",
        re.MULTILINE,
    )
    SYNTAX_ERROR_PATTERN = re.compile(
        r"^\s*File \"([^\"]+)\", line (\d+).*\n"
        r"(?:.*\n)?"
        r"\s*\^+\n"
        r"(SyntaxError|IndentationError|TabError):\s*(.*)",
        re.MULTILINE,
    )
    CODE_BLOCK_PATTERN = re.compile(r"```(?:python|py)?\n(.*?)```", re.DOTALL)

    def __init__(self) -> None:
        """Initialize the TracebackParser."""
        pass

    def contains_traceback(self, text: str) -> bool:
        """Check if text contains a Python traceback.

        Args:
            text: Text to check for tracebacks

        Returns:
            True if a traceback is detected, False otherwise
        """
        if not text:
            return False

        # Check for standard traceback header
        if self.TRACEBACK_HEADER.search(text):
            return True

        # Check for syntax errors
        if self.SYNTAX_ERROR_PATTERN.search(text):
            return True

        # Check in code blocks
        for match in self.CODE_BLOCK_PATTERN.finditer(text):
            block_content = match.group(1)
            if self.TRACEBACK_HEADER.search(block_content):
                return True
            if self.SYNTAX_ERROR_PATTERN.search(block_content):
                return True

        return False

    def parse(self, text: str) -> ParsedTraceback:
        """Parse a Python traceback from text.

        Args:
            text: Text containing a Python traceback

        Returns:
            ParsedTraceback with extracted information

        Raises:
            TracebackParseError: If no valid traceback is found
        """
        if not text:
            raise TracebackParseError("Empty text provided")

        # Try to extract from code blocks first
        extracted_text = self._extract_from_code_blocks(text) or text

        # Check for syntax errors first (special format)
        syntax_match = self.SYNTAX_ERROR_PATTERN.search(extracted_text)
        if syntax_match:
            return self._parse_syntax_error(syntax_match, text)

        # Find traceback header
        header_match = self.TRACEBACK_HEADER.search(extracted_text)
        if not header_match:
            raise TracebackParseError("No traceback header found")

        # Extract the traceback portion
        traceback_start = header_match.start()
        traceback_text = extracted_text[traceback_start:]

        # Check for chained exceptions
        chain_match = self.CHAINED_PATTERN.search(traceback_text)
        if chain_match:
            return self._parse_chained(traceback_text, text)

        # Parse single traceback
        return self._parse_single(traceback_text, text)

    def extract_all(self, text: str) -> list[ParsedTraceback]:
        """Extract all tracebacks from text (for chained exceptions).

        Args:
            text: Text potentially containing multiple tracebacks

        Returns:
            List of ParsedTraceback objects, ordered from outermost to innermost
        """
        tracebacks: list[ParsedTraceback] = []

        # Extract from code blocks
        extracted_text = self._extract_from_code_blocks(text) or text

        # Split by chain markers
        chain_splits = self.CHAINED_PATTERN.split(extracted_text)

        for segment in chain_splits:
            if self.TRACEBACK_HEADER.search(segment):
                try:
                    tb = self._parse_single(segment, segment)
                    tracebacks.append(tb)
                except TracebackParseError:
                    continue

        return tracebacks

    def _extract_from_code_blocks(self, text: str) -> str | None:
        """Extract traceback from code blocks if present.

        Args:
            text: Text potentially containing code blocks

        Returns:
            Content of first code block with traceback, or None
        """
        for match in self.CODE_BLOCK_PATTERN.finditer(text):
            block_content = match.group(1)
            if self.TRACEBACK_HEADER.search(block_content) or self.SYNTAX_ERROR_PATTERN.search(
                block_content
            ):
                return block_content
        return None

    def _parse_single(self, traceback_text: str, raw_text: str) -> ParsedTraceback:
        """Parse a single (non-chained) traceback.

        Args:
            traceback_text: Text containing just the traceback
            raw_text: Original raw text

        Returns:
            ParsedTraceback

        Raises:
            TracebackParseError: If parsing fails
        """
        # Extract frames
        frames = self._extract_frames(traceback_text)

        # Extract exception info
        exception_type, exception_message = self._extract_exception(traceback_text)

        if not exception_type:
            raise TracebackParseError("Could not extract exception type")

        return ParsedTraceback(
            exception_type=exception_type,
            exception_message=exception_message,
            frames=tuple(frames),
            raw_text=raw_text,
            is_chained=False,
            cause=None,
        )

    def _parse_chained(self, traceback_text: str, raw_text: str) -> ParsedTraceback:
        """Parse a chained exception traceback.

        Args:
            traceback_text: Text containing chained tracebacks
            raw_text: Original raw text

        Returns:
            ParsedTraceback with cause chain (outermost exception with cause pointing to inner)
        """
        # Split by chain markers
        segments = self.CHAINED_PATTERN.split(traceback_text)
        segments = [s.strip() for s in segments if s.strip()]

        if len(segments) < 2:
            # Fall back to single parse
            return self._parse_single(traceback_text, raw_text)

        # Parse from first to last (cause to effect)
        # In a chained traceback:
        #   - First segment is the original/cause exception
        #   - Last segment is the final/outer exception
        # We build the chain so each later exception has the earlier as its cause
        cause_tb: ParsedTraceback | None = None

        for segment in segments:
            if not self.TRACEBACK_HEADER.search(segment):
                continue

            frames = self._extract_frames(segment)
            exception_type, exception_message = self._extract_exception(segment)

            if not exception_type:
                continue

            cause_tb = ParsedTraceback(
                exception_type=exception_type,
                exception_message=exception_message,
                frames=tuple(frames),
                raw_text=segment,
                is_chained=cause_tb is not None,
                cause=cause_tb,
            )

        if cause_tb is None:
            raise TracebackParseError("Could not parse any exceptions from chain")

        return cause_tb

    def _parse_syntax_error(
        self,
        match: re.Match[str],
        raw_text: str,
    ) -> ParsedTraceback:
        """Parse a syntax error traceback.

        Args:
            match: Regex match for syntax error pattern
            raw_text: Original raw text

        Returns:
            ParsedTraceback for syntax error
        """
        file_path = match.group(1)
        line_number = int(match.group(2))
        exception_type = match.group(3)
        exception_message = match.group(4)

        # Create a single frame for the syntax error location
        frame = StackFrame(
            file_path=file_path,
            line_number=line_number,
            function_name="<module>",
            code_line=None,
        )

        return ParsedTraceback(
            exception_type=exception_type,
            exception_message=exception_message,
            frames=(frame,),
            raw_text=raw_text,
            is_chained=False,
            cause=None,
        )

    def _extract_frames(self, traceback_text: str) -> list[StackFrame]:
        """Extract stack frames from traceback text.

        Args:
            traceback_text: Traceback text to parse

        Returns:
            List of StackFrame objects
        """
        frames: list[StackFrame] = []
        lines = traceback_text.splitlines()

        i = 0
        while i < len(lines):
            line = lines[i]
            frame_match = self.FRAME_PATTERN.match(line)

            if frame_match:
                file_path = frame_match.group(1)
                line_number = int(frame_match.group(2))
                function_name = frame_match.group(3) or "<module>"

                # Try to get the code line (next line, indented)
                code_line = None
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    # Check if it's a code line (indented but not a File line)
                    if next_line.startswith("    ") and not next_line.strip().startswith("File"):
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

    def _extract_exception(self, traceback_text: str) -> tuple[str, str]:
        """Extract exception type and message from traceback.

        Args:
            traceback_text: Traceback text to parse

        Returns:
            Tuple of (exception_type, exception_message)
        """
        lines = traceback_text.splitlines()

        # Search from the end for the exception line
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue

            # Skip frame lines and other non-exception lines
            if line.startswith("File ") or line.startswith("^"):
                continue

            # Try to match exception with message
            exc_match = self.EXCEPTION_PATTERN.match(line)
            if exc_match:
                return (exc_match.group(1), exc_match.group(2))

            # Try to match exception without message
            exc_no_msg_match = self.EXCEPTION_NO_MSG_PATTERN.match(line)
            if exc_no_msg_match:
                return (exc_no_msg_match.group(1), "")

        return ("", "")
