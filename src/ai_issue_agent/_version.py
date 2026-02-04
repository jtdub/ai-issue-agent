"""Version information for AI Issue Agent."""

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    try:
        from importlib.metadata import version as get_version
    except ImportError:
        from importlib_metadata import version as get_version  # type: ignore[import-not-found]
else:
    from importlib_metadata import version as get_version  # type: ignore[import-not-found]


def get_version_from_pyproject() -> str:
    """
    Get version from pyproject.toml.

    Returns:
        Version string

    Raises:
        RuntimeError: If version cannot be determined
    """
    try:
        # Try to get version from installed package metadata
        return get_version("ai-issue-agent")
    except Exception:
        # Fall back to reading pyproject.toml directly
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[import-not-found]

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
                return str(data["tool"]["poetry"]["version"])

        raise RuntimeError("Could not determine package version")


__version__ = get_version_from_pyproject()

__all__ = ["__version__"]
