"""Configuration loader with YAML parsing and environment variable substitution."""

import os
import re
from pathlib import Path

import yaml

from .schema import AgentConfig


def substitute_env_vars(text: str) -> str:
    """
    Replace ${VAR_NAME} patterns with environment variable values.

    Args:
        text: Text containing ${VAR_NAME} patterns

    Returns:
        Text with environment variables substituted

    Raises:
        ValueError: If a referenced environment variable is not found
    """

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        value = os.environ.get(var_name)
        if value is None:
            raise ValueError(f"Environment variable {var_name} not found")
        return value

    return re.sub(r"\$\{([^}]+)\}", replacer, text)


def load_config(path: Path) -> AgentConfig:
    """
    Load configuration from YAML file with environment variable substitution.

    Args:
        path: Path to YAML configuration file

    Returns:
        Validated AgentConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If environment variables are missing or config is invalid
        ValidationError: If config doesn't match schema
    """
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open() as f:
        raw_yaml = f.read()

    # Substitute environment variables
    yaml_with_env = substitute_env_vars(raw_yaml)

    # Parse YAML
    config_dict = yaml.safe_load(yaml_with_env)

    # Validate and construct Pydantic model
    config = AgentConfig.model_validate(config_dict)

    # Additional cross-field validation
    validate_config(config)

    return config


def validate_config(config: AgentConfig) -> None:
    """
    Perform additional cross-field validation.

    Ensures that provider-specific configuration is present when
    a provider is selected.

    Args:
        config: Configuration to validate

    Raises:
        ValueError: If provider-specific config is missing
    """
    # Ensure provider-specific config is present
    if config.chat.provider == "slack" and config.chat.slack is None:
        raise ValueError("Slack provider selected but slack config missing")

    if config.vcs.provider == "github" and config.vcs.github is None:
        raise ValueError("GitHub provider selected but github config missing")

    if config.llm.provider == "openai" and config.llm.openai is None:
        raise ValueError("OpenAI provider selected but openai config missing")
    elif config.llm.provider == "anthropic" and config.llm.anthropic is None:
        raise ValueError("Anthropic provider selected but anthropic config missing")
    elif config.llm.provider == "ollama" and config.llm.ollama is None:
        raise ValueError("Ollama provider selected but ollama config missing")
