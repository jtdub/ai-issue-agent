"""Pydantic models for configuration schema."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SlackConfig(BaseModel):
    """Slack-specific configuration."""

    bot_token: str
    app_token: str
    channels: list[str] = []
    processing_reaction: str = "eyes"
    complete_reaction: str = "white_check_mark"
    error_reaction: str = "x"

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        """Validate Slack bot token format."""
        if not v.startswith("xoxb-"):
            raise ValueError("Bot token must start with xoxb-")
        return v

    @field_validator("app_token")
    @classmethod
    def validate_app_token(cls, v: str) -> str:
        """Validate Slack app token format."""
        if not v.startswith("xapp-"):
            raise ValueError("App token must start with xapp-")
        return v


class GitHubConfig(BaseModel):
    """GitHub-specific configuration."""

    default_repo: str
    clone_dir: Path = Path("/tmp/ai-issue-agent/repos")  # noqa: S108
    clone_cache_ttl: int = 3600
    default_labels: list[str] = ["auto-triaged"]
    gh_path: str | None = None
    allowed_repos: list[str] = []

    @field_validator("default_repo")
    @classmethod
    def validate_default_repo(cls, v: str) -> str:
        """Validate repository name format."""
        from ..utils.security import validate_repo_name

        if not validate_repo_name(v):
            raise ValueError(f"Invalid repository format: {v}. Expected: owner/repo")
        return v

    @field_validator("allowed_repos")
    @classmethod
    def validate_allowed_repos(cls, v: list[str]) -> list[str]:
        """Validate allowed repository names."""
        from ..utils.security import validate_repo_name

        for repo in v:
            # Allow wildcards like "myorg/*"
            if "*" not in repo and not validate_repo_name(repo):
                raise ValueError(f"Invalid repository format: {repo}")
        return v


class OpenAIConfig(BaseModel):
    """OpenAI-specific configuration."""

    api_key: str
    model: str = "gpt-4-turbo-preview"
    max_tokens: int = 4096
    temperature: float = 0.3


class AnthropicConfig(BaseModel):
    """Anthropic-specific configuration."""

    api_key: str
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4096
    temperature: float = 0.3


class OllamaConfig(BaseModel):
    """Ollama-specific configuration."""

    base_url: str = "http://localhost:11434"
    model: str = "llama2:70b"
    timeout: int = 120
    allow_remote_host: bool = False

    @model_validator(mode="after")
    def check_remote_host(self) -> "OllamaConfig":
        """Validate Ollama URL and check for SSRF prevention."""
        from urllib.parse import urlparse

        from ..utils.security import validate_ollama_url

        if not validate_ollama_url(self.base_url, allow_remote=self.allow_remote_host):
            parsed = urlparse(self.base_url)
            host = parsed.hostname
            if not self.allow_remote_host:
                raise ValueError(
                    f"Ollama host {host} not allowed. "
                    f"Set allow_remote_host=true to use non-localhost hosts."
                )
            else:
                raise ValueError(f"Invalid Ollama URL: {self.base_url}")
        return self


class MatchingConfig(BaseModel):
    """Issue matching configuration."""

    confidence_threshold: float = Field(0.85, ge=0.0, le=1.0)
    max_search_results: int = Field(20, ge=1, le=100)
    include_closed: bool = True
    search_cache_ttl: int = Field(300, ge=0)


class AnalysisConfig(BaseModel):
    """Code analysis configuration."""

    context_lines: int = Field(15, ge=1, le=100)
    max_files: int = Field(10, ge=1, le=50)
    skip_paths: list[str] = ["/usr/lib/python", "site-packages"]
    include_files: list[str] = ["README.md"]


class FileLoggingConfig(BaseModel):
    """File logging configuration."""

    enabled: bool = False
    path: Path = Path("/var/log/ai-issue-agent/agent.log")
    rotation: str = "10 MB"
    retention: int = Field(7, ge=1, description="Retention period in days")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["json", "console"] = "json"
    file: FileLoggingConfig = FileLoggingConfig()


class RuntimeConfig(BaseModel):
    """Runtime configuration."""

    max_concurrent: int = Field(5, ge=1, le=50, description="Max concurrent message processing")
    processing_timeout: int = Field(300, ge=30, le=600, description="Pipeline timeout in seconds")


class RetryConfig(BaseModel):
    """Retry configuration for transient failures."""

    max_attempts: int = Field(3, ge=1, le=10)
    initial_delay: float = Field(1.0, ge=0.1, le=10.0)
    max_delay: float = Field(30.0, ge=1.0, le=300.0)
    exponential_base: float = Field(2.0, ge=1.5, le=4.0)


class ChatConfig(BaseModel):
    """Chat provider configuration."""

    provider: Literal["slack", "discord", "teams"]
    slack: SlackConfig | None = None


class VCSConfig(BaseModel):
    """Version control system configuration."""

    provider: Literal["github", "gitlab", "bitbucket"]
    github: GitHubConfig | None = None
    channel_repos: dict[str, str] = {}
    allow_public_repos: bool = False

    @field_validator("channel_repos")
    @classmethod
    def validate_channel_repos(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate channel-to-repository mappings."""
        from ..utils.security import validate_repo_name

        for channel, repo in v.items():
            if not validate_repo_name(repo):
                raise ValueError(f"Invalid repository format for {channel}: {repo}")
        return v


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: Literal["openai", "anthropic", "ollama"]
    openai: OpenAIConfig | None = None
    anthropic: AnthropicConfig | None = None
    ollama: OllamaConfig | None = None


class AgentConfig(BaseSettings):
    """Root configuration for AI Issue Agent."""

    chat: ChatConfig
    vcs: VCSConfig
    llm: LLMConfig
    matching: MatchingConfig = MatchingConfig()
    analysis: AnalysisConfig = AnalysisConfig()
    logging: LoggingConfig = LoggingConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    retry: RetryConfig = RetryConfig()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
    )
