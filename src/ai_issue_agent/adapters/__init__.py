"""Concrete implementations of provider interfaces."""

from .chat.slack import SlackAdapter
from .llm.anthropic import AnthropicAdapter
from .vcs.github import GitHubAdapter

__all__ = [
    "AnthropicAdapter",
    "GitHubAdapter",
    "SlackAdapter",
]
