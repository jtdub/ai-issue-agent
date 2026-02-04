"""Data models for Python tracebacks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StackFrame:
    """A single frame in a Python stack trace."""

    file_path: str
    line_number: int
    function_name: str
    code_line: str | None = None

    @property
    def is_stdlib(self) -> bool:
        """Check if this frame is from Python standard library."""
        stdlib_indicators = [
            "/lib/python",
            "/lib64/python",
            "\\lib\\python",  # Windows
            "<frozen",
            "<built-in",
        ]
        return any(indicator in self.file_path for indicator in stdlib_indicators)

    @property
    def is_site_packages(self) -> bool:
        """Check if this frame is from third-party packages."""
        return "site-packages" in self.file_path or "dist-packages" in self.file_path

    @property
    def normalized_path(self) -> str:
        """
        Path relative to project root, without absolute prefixes.

        Strips common absolute path prefixes to make paths more portable.
        """
        path = self.file_path

        # Remove common absolute path prefixes
        prefixes_to_strip = [
            "/usr/local/",
            "/usr/",
            "/home/",
            "/Users/",
            "C:\\",
            "C:/",
        ]

        for prefix in prefixes_to_strip:
            if path.startswith(prefix):
                # Find the first directory that looks like a project root
                parts = path.split("/") if "/" in path else path.split("\\")
                # Keep the last few meaningful parts
                if len(parts) > 2:
                    path = "/".join(parts[-3:])
                break

        return path


@dataclass(frozen=True)
class ParsedTraceback:
    """A fully parsed Python traceback."""

    exception_type: str  # e.g., "ValueError"
    exception_message: str  # e.g., "invalid literal for int()"
    frames: tuple[StackFrame, ...]
    raw_text: str  # Original traceback text
    is_chained: bool = False  # Part of exception chain
    cause: "ParsedTraceback | None" = None  # __cause__ exception

    @property
    def innermost_frame(self) -> StackFrame:
        """The frame where the exception was raised (last frame)."""
        if not self.frames:
            raise ValueError("Traceback has no frames")
        return self.frames[-1]

    @property
    def project_frames(self) -> tuple[StackFrame, ...]:
        """Frames from project code (not stdlib/site-packages)."""
        return tuple(
            frame
            for frame in self.frames
            if not frame.is_stdlib and not frame.is_site_packages
        )

    @property
    def signature(self) -> str:
        """
        Unique signature for deduplication.

        Format: 'ExceptionType: message'
        """
        return f"{self.exception_type}: {self.exception_message}"
