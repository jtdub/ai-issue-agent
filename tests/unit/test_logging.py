"""Tests for the logging configuration module."""

from pathlib import Path

from ai_issue_agent.utils.logging import (
    LogFormat,
    LogLevel,
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    sanitize_log_value,
    secret_sanitizer,
    unbind_context,
)


class TestSanitizeLogValue:
    """Tests for sanitize_log_value function."""

    def test_sanitize_string_with_slack_token(self) -> None:
        """Test that Slack tokens are redacted."""
        text = "Bot token: xoxb-123-456-abc"
        result = sanitize_log_value(text)
        assert "xoxb" not in result
        assert "[REDACTED]" in result

    def test_sanitize_string_with_github_token(self) -> None:
        """Test that GitHub tokens are redacted."""
        text = "Token: ghp_1234567890123456789012345678901234567890"
        result = sanitize_log_value(text)
        assert "ghp_" not in result
        assert "[REDACTED]" in result

    def test_sanitize_string_without_secrets(self) -> None:
        """Test that strings without secrets are unchanged."""
        text = "Normal log message without secrets"
        result = sanitize_log_value(text)
        assert result == text

    def test_sanitize_nested_dict(self) -> None:
        """Test that nested dicts are recursively sanitized."""
        data = {
            "message": "test",
            "nested": {
                "token": "xoxb-secret-token-here",
            },
        }
        result = sanitize_log_value(data)
        assert "[REDACTED]" in result["nested"]["token"]

    def test_sanitize_list(self) -> None:
        """Test that lists are sanitized."""
        data = ["normal", "xoxb-secret-token"]
        result = sanitize_log_value(data)
        assert result[0] == "normal"
        assert "[REDACTED]" in result[1]

    def test_sanitize_non_string(self) -> None:
        """Test that non-strings are passed through."""
        assert sanitize_log_value(123) == 123
        assert sanitize_log_value(12.5) == 12.5
        assert sanitize_log_value(True) is True
        assert sanitize_log_value(None) is None


class TestSecretSanitizer:
    """Tests for the secret_sanitizer processor."""

    def test_sanitizer_redacts_secrets(self) -> None:
        """Test that the processor redacts secrets."""
        event_dict = {
            "event": "test",
            "token": "sk-ant-1234567890abcdef1234567890abcdef12345678",
        }
        result = secret_sanitizer(None, "info", event_dict)  # type: ignore
        assert "[REDACTED]" in result["token"]

    def test_sanitizer_preserves_non_secrets(self) -> None:
        """Test that non-secret values are preserved."""
        event_dict = {
            "event": "test_event",
            "level": "info",
            "count": 42,
        }
        result = secret_sanitizer(None, "info", event_dict)  # type: ignore
        assert result["event"] == "test_event"
        assert result["level"] == "info"
        assert result["count"] == 42


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_with_console_format(self) -> None:
        """Test configuration with console format."""
        configure_logging(level=LogLevel.DEBUG, log_format=LogFormat.CONSOLE)
        # Should not raise

    def test_configure_with_json_format(self) -> None:
        """Test configuration with JSON format."""
        configure_logging(level=LogLevel.INFO, log_format=LogFormat.JSON)
        # Should not raise

    def test_configure_with_string_values(self) -> None:
        """Test configuration with string values."""
        configure_logging(level="WARNING", log_format="json")
        # Should not raise

    def test_configure_with_file_logging(self, tmp_path: Path) -> None:
        """Test configuration with file logging."""
        log_file = tmp_path / "test.log"
        configure_logging(
            level=LogLevel.INFO,
            log_format=LogFormat.JSON,
            file_path=log_file,
            file_enabled=True,
        )
        # File should be creatable (directory exists)
        assert tmp_path.exists()


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_bound_logger(self) -> None:
        """Test that get_logger returns a structlog logger."""
        configure_logging()  # Ensure logging is configured
        log = get_logger("test")
        assert log is not None


class TestContextFunctions:
    """Tests for context binding functions."""

    def test_bind_and_clear_context(self) -> None:
        """Test binding and clearing context."""
        # This should not raise
        bind_context(channel_id="C123", user_id="U456")
        clear_context()

    def test_unbind_context(self) -> None:
        """Test unbinding specific context keys."""
        bind_context(key1="value1", key2="value2")
        unbind_context("key1")
        clear_context()


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_levels(self) -> None:
        """Test that all expected log levels exist."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


class TestLogFormat:
    """Tests for LogFormat enum."""

    def test_log_formats(self) -> None:
        """Test that all expected formats exist."""
        assert LogFormat.JSON.value == "json"
        assert LogFormat.CONSOLE.value == "console"
