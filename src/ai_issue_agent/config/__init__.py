"""Configuration loading and validation."""

from .loader import load_config
from .schema import (
    AgentConfig,
    AnalysisConfig,
    AnthropicConfig,
    ChatConfig,
    GitHubConfig,
    LLMConfig,
    MatchingConfig,
    OllamaConfig,
    OpenAIConfig,
    SlackConfig,
    VCSConfig,
)

__all__ = [
    # Loader
    "load_config",
    # Root config
    "AgentConfig",
    # Top-level configs
    "ChatConfig",
    "VCSConfig",
    "LLMConfig",
    "MatchingConfig",
    "AnalysisConfig",
    # Provider-specific configs
    "SlackConfig",
    "GitHubConfig",
    "OpenAIConfig",
    "AnthropicConfig",
    "OllamaConfig",
]
