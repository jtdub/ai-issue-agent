"""Protocol definitions for pluggable adapters."""

from .chat import ChatProvider
from .llm import LLMProvider
from .vcs import VCSProvider

__all__ = ["ChatProvider", "LLMProvider", "VCSProvider"]
