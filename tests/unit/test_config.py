"""Tests for configuration loading and validation."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
from pydantic import ValidationError

from ai_issue_agent.config.loader import load_config, substitute_env_vars, validate_config
from ai_issue_agent.config.schema import (
    AgentConfig,
    AnalysisConfig,
    AnthropicConfig,
    ChatConfig,
    GitHubConfig,
    LLMConfig,
    MatchingConfig,
    OllamaConfig,
    SlackConfig,
    VCSConfig,
)


class TestSubstituteEnvVars:
    """Test environment variable substitution."""

    def test_substitute_single_var(self):
        """Test substituting a single environment variable."""
        os.environ["TEST_VAR"] = "test_value"
        result = substitute_env_vars("Value is ${TEST_VAR}")
        assert result == "Value is test_value"
        del os.environ["TEST_VAR"]

    def test_substitute_multiple_vars(self):
        """Test substituting multiple environment variables."""
        os.environ["VAR1"] = "value1"
        os.environ["VAR2"] = "value2"
        result = substitute_env_vars("${VAR1} and ${VAR2}")
        assert result == "value1 and value2"
        del os.environ["VAR1"]
        del os.environ["VAR2"]

    def test_missing_env_var_raises(self):
        """Test that missing environment variables raise ValueError."""
        with pytest.raises(ValueError, match="Environment variable MISSING not found"):
            substitute_env_vars("Value is ${MISSING}")

    def test_no_substitution_needed(self):
        """Test text without environment variables passes through unchanged."""
        result = substitute_env_vars("plain text without vars")
        assert result == "plain text without vars"


class TestSlackConfig:
    """Test SlackConfig validation."""

    def test_valid_slack_config(self):
        """Test creating valid Slack config."""
        config = SlackConfig(
            bot_token="xoxb-123-456-abc",
            app_token="xapp-1-A0-abc",
            channels=["#errors"],
        )
        assert config.bot_token == "xoxb-123-456-abc"
        assert config.app_token == "xapp-1-A0-abc"
        assert config.channels == ["#errors"]

    def test_invalid_bot_token_rejected(self):
        """Test that invalid bot token format is rejected."""
        with pytest.raises(ValidationError, match="Bot token must start with xoxb-"):
            SlackConfig(
                bot_token="invalid-token",
                app_token="xapp-1-A0-abc",
            )

    def test_invalid_app_token_rejected(self):
        """Test that invalid app token format is rejected."""
        with pytest.raises(ValidationError, match="App token must start with xapp-"):
            SlackConfig(
                bot_token="xoxb-123-456-abc",
                app_token="invalid-token",
            )

    def test_default_reactions(self):
        """Test default reaction values."""
        config = SlackConfig(
            bot_token="xoxb-123-456-abc",
            app_token="xapp-1-A0-abc",
        )
        assert config.processing_reaction == "eyes"
        assert config.complete_reaction == "white_check_mark"
        assert config.error_reaction == "x"


class TestGitHubConfig:
    """Test GitHubConfig validation."""

    def test_valid_github_config(self):
        """Test creating valid GitHub config."""
        config = GitHubConfig(default_repo="owner/repo")
        assert config.default_repo == "owner/repo"
        assert config.clone_cache_ttl == 3600
        assert config.default_labels == ["auto-triaged"]

    def test_invalid_repo_name_rejected(self):
        """Test that invalid repository names are rejected."""
        invalid_repos = [
            "invalid",  # Missing slash
            "owner/",  # Missing repo name
            "/repo",  # Missing owner
            "owner/repo; rm -rf /",  # Command injection attempt
            "owner/repo$(whoami)",  # Command injection attempt
        ]

        for repo in invalid_repos:
            with pytest.raises(ValidationError, match="Invalid repository format"):
                GitHubConfig(default_repo=repo)

    def test_allowed_repos_with_wildcard(self):
        """Test allowed_repos with wildcard patterns."""
        config = GitHubConfig(
            default_repo="myorg/myrepo",
            allowed_repos=["myorg/*", "otherorg/specific-repo"],
        )
        assert "myorg/*" in config.allowed_repos
        assert "otherorg/specific-repo" in config.allowed_repos

    def test_invalid_allowed_repo_rejected(self):
        """Test that invalid repo in allowed_repos is rejected."""
        with pytest.raises(ValidationError, match="Invalid repository format"):
            GitHubConfig(
                default_repo="owner/repo",
                allowed_repos=["owner/repo", "invalid-format"],
            )


class TestOllamaConfig:
    """Test OllamaConfig validation and SSRF prevention."""

    def test_localhost_allowed(self):
        """Test that localhost URLs are allowed."""
        config = OllamaConfig(base_url="http://localhost:11434")
        assert config.base_url == "http://localhost:11434"

    def test_127_0_0_1_allowed(self):
        """Test that 127.0.0.1 URLs are allowed."""
        config = OllamaConfig(base_url="http://127.0.0.1:11434")
        assert config.base_url == "http://127.0.0.1:11434"

    def test_remote_blocked_by_default(self):
        """Test that non-localhost URLs are blocked by default."""
        with pytest.raises(ValidationError):
            OllamaConfig(base_url="http://192.168.1.100:11434")

    def test_remote_allowed_with_flag(self):
        """Test that non-localhost URLs are allowed with explicit flag."""
        config = OllamaConfig(
            base_url="http://192.168.1.100:11434",
            allow_remote_host=True,
        )
        assert config.base_url == "http://192.168.1.100:11434"
        assert config.allow_remote_host is True

    def test_ssrf_prevention_aws_metadata(self):
        """Test SSRF prevention for AWS metadata endpoint."""
        with pytest.raises(ValidationError):
            OllamaConfig(base_url="http://169.254.169.254/latest/meta-data/")

    def test_default_values(self):
        """Test default configuration values."""
        config = OllamaConfig()
        assert config.base_url == "http://localhost:11434"
        assert config.model == "llama2:70b"
        assert config.timeout == 120
        assert config.allow_remote_host is False


class TestVCSConfig:
    """Test VCSConfig validation."""

    def test_valid_vcs_config(self):
        """Test creating valid VCS config."""
        github_config = GitHubConfig(default_repo="owner/repo")
        config = VCSConfig(provider="github", github=github_config)
        assert config.provider == "github"
        assert config.github is not None

    def test_channel_repos_validation(self):
        """Test channel_repos validation."""
        github_config = GitHubConfig(default_repo="owner/repo")
        config = VCSConfig(
            provider="github",
            github=github_config,
            channel_repos={
                "#frontend": "owner/frontend",
                "#backend": "owner/backend",
            },
        )
        assert len(config.channel_repos) == 2
        assert config.channel_repos["#frontend"] == "owner/frontend"

    def test_invalid_channel_repo_rejected(self):
        """Test that invalid repo in channel_repos is rejected."""
        github_config = GitHubConfig(default_repo="owner/repo")
        with pytest.raises(ValidationError, match="Invalid repository format"):
            VCSConfig(
                provider="github",
                github=github_config,
                channel_repos={"#test": "invalid-format"},
            )


class TestMatchingConfig:
    """Test MatchingConfig validation."""

    def test_default_values(self):
        """Test default matching configuration values."""
        config = MatchingConfig()
        assert config.confidence_threshold == 0.85
        assert config.max_search_results == 20
        assert config.include_closed is True
        assert config.search_cache_ttl == 300

    def test_confidence_threshold_bounds(self):
        """Test that confidence_threshold is bounded between 0 and 1."""
        # Valid values
        MatchingConfig(confidence_threshold=0.0)
        MatchingConfig(confidence_threshold=0.5)
        MatchingConfig(confidence_threshold=1.0)

        # Invalid values
        with pytest.raises(ValidationError):
            MatchingConfig(confidence_threshold=-0.1)
        with pytest.raises(ValidationError):
            MatchingConfig(confidence_threshold=1.1)

    def test_max_search_results_bounds(self):
        """Test that max_search_results is bounded."""
        # Valid values
        MatchingConfig(max_search_results=1)
        MatchingConfig(max_search_results=50)
        MatchingConfig(max_search_results=100)

        # Invalid values
        with pytest.raises(ValidationError):
            MatchingConfig(max_search_results=0)
        with pytest.raises(ValidationError):
            MatchingConfig(max_search_results=101)


class TestAnalysisConfig:
    """Test AnalysisConfig validation."""

    def test_default_values(self):
        """Test default analysis configuration values."""
        config = AnalysisConfig()
        assert config.context_lines == 15
        assert config.max_files == 10
        assert "/usr/lib/python" in config.skip_paths
        assert "README.md" in config.include_files

    def test_context_lines_bounds(self):
        """Test that context_lines is bounded."""
        # Valid values
        AnalysisConfig(context_lines=1)
        AnalysisConfig(context_lines=50)
        AnalysisConfig(context_lines=100)

        # Invalid values
        with pytest.raises(ValidationError):
            AnalysisConfig(context_lines=0)
        with pytest.raises(ValidationError):
            AnalysisConfig(context_lines=101)

    def test_max_files_bounds(self):
        """Test that max_files is bounded."""
        # Valid values
        AnalysisConfig(max_files=1)
        AnalysisConfig(max_files=25)
        AnalysisConfig(max_files=50)

        # Invalid values
        with pytest.raises(ValidationError):
            AnalysisConfig(max_files=0)
        with pytest.raises(ValidationError):
            AnalysisConfig(max_files=51)


class TestLoadConfig:
    """Test configuration loading from YAML."""

    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        # Set environment variables
        os.environ["TEST_SLACK_BOT_TOKEN"] = "xoxb-test-123"
        os.environ["TEST_SLACK_APP_TOKEN"] = "xapp-test-456"
        os.environ["TEST_ANTHROPIC_KEY"] = "sk-ant-test"

        yaml_content = """
chat:
  provider: slack
  slack:
    bot_token: ${TEST_SLACK_BOT_TOKEN}
    app_token: ${TEST_SLACK_APP_TOKEN}
    channels:
      - "#errors"

vcs:
  provider: github
  github:
    default_repo: "owner/repo"

llm:
  provider: anthropic
  anthropic:
    api_key: ${TEST_ANTHROPIC_KEY}
    model: "claude-3-sonnet-20240229"
"""

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = load_config(Path(f.name))
                assert config.chat.provider == "slack"
                assert config.chat.slack.bot_token == "xoxb-test-123"
                assert config.vcs.provider == "github"
                assert config.vcs.github.default_repo == "owner/repo"
                assert config.llm.provider == "anthropic"
            finally:
                Path(f.name).unlink()
                del os.environ["TEST_SLACK_BOT_TOKEN"]
                del os.environ["TEST_SLACK_APP_TOKEN"]
                del os.environ["TEST_ANTHROPIC_KEY"]

    def test_load_config_missing_file(self):
        """Test that loading non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.yaml"))

    def test_load_config_missing_env_var(self):
        """Test that missing environment variable raises error."""
        yaml_content = """
chat:
  provider: slack
  slack:
    bot_token: ${MISSING_VAR}
    app_token: xapp-test
"""

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with pytest.raises(ValueError, match="Environment variable MISSING_VAR not found"):
                    load_config(Path(f.name))
            finally:
                Path(f.name).unlink()


class TestValidateConfig:
    """Test cross-field configuration validation."""

    def test_slack_provider_without_slack_config(self):
        """Test that selecting slack provider without slack config raises error."""
        chat_config = ChatConfig(provider="slack", slack=None)
        vcs_config = VCSConfig(provider="github", github=GitHubConfig(default_repo="owner/repo"))
        llm_config = LLMConfig(provider="anthropic", anthropic=AnthropicConfig(api_key="test"))

        config = AgentConfig(chat=chat_config, vcs=vcs_config, llm=llm_config)

        with pytest.raises(ValueError, match="Slack provider selected but slack config missing"):
            validate_config(config)

    def test_github_provider_without_github_config(self):
        """Test that selecting github provider without github config raises error."""
        chat_config = ChatConfig(
            provider="slack",
            slack=SlackConfig(bot_token="xoxb-test", app_token="xapp-test"),
        )
        vcs_config = VCSConfig(provider="github", github=None)
        llm_config = LLMConfig(provider="anthropic", anthropic=AnthropicConfig(api_key="test"))

        config = AgentConfig(chat=chat_config, vcs=vcs_config, llm=llm_config)

        with pytest.raises(ValueError, match="GitHub provider selected but github config missing"):
            validate_config(config)

    def test_openai_provider_without_openai_config(self):
        """Test that selecting openai provider without openai config raises error."""
        chat_config = ChatConfig(
            provider="slack",
            slack=SlackConfig(bot_token="xoxb-test", app_token="xapp-test"),
        )
        vcs_config = VCSConfig(provider="github", github=GitHubConfig(default_repo="owner/repo"))
        llm_config = LLMConfig(provider="openai", openai=None)

        config = AgentConfig(chat=chat_config, vcs=vcs_config, llm=llm_config)

        with pytest.raises(ValueError, match="OpenAI provider selected but openai config missing"):
            validate_config(config)

    def test_valid_config_passes(self):
        """Test that valid configuration passes validation."""
        chat_config = ChatConfig(
            provider="slack",
            slack=SlackConfig(bot_token="xoxb-test", app_token="xapp-test"),
        )
        vcs_config = VCSConfig(provider="github", github=GitHubConfig(default_repo="owner/repo"))
        llm_config = LLMConfig(provider="anthropic", anthropic=AnthropicConfig(api_key="test"))

        config = AgentConfig(chat=chat_config, vcs=vcs_config, llm=llm_config)

        # Should not raise
        validate_config(config)
