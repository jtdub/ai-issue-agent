"""Structured logging configuration with secret sanitization.

This module provides comprehensive logging configuration for the AI Issue Agent:
- Configurable log levels and output formats (JSON/console)
- Automatic secret sanitization in log output
- Context injection for correlation
- File and console output support

See docs/admin-guide/monitoring.md for operational guidance.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

import structlog
from structlog.typing import WrappedLogger

# Re-use the SecretRedactor for log sanitization
from ai_issue_agent.utils.security import SecretRedactor


class LogFormat(StrEnum):
    """Log output format options."""

    JSON = "json"
    CONSOLE = "console"


class LogLevel(StrEnum):
    """Log level options."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class FileLogConfig:
    """File logging configuration."""

    enabled: bool = False
    path: Path = field(default_factory=lambda: Path("/var/log/ai-issue-agent/agent.log"))
    rotation: str = "10 MB"
    retention: int = 7  # days


@dataclass
class LogConfig:
    """Logging configuration."""

    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.JSON
    file: FileLogConfig = field(default_factory=FileLogConfig)


# Global redactor instance for log sanitization
_redactor: SecretRedactor | None = None


def _get_redactor() -> SecretRedactor:
    """Get or create the global secret redactor."""
    global _redactor
    if _redactor is None:
        _redactor = SecretRedactor(placeholder="[REDACTED]")
    return _redactor


def sanitize_log_value(value: Any) -> Any:
    """Recursively sanitize secrets from log values.

    Args:
        value: Value to sanitize (can be nested dict/list/str)

    Returns:
        Sanitized value with secrets redacted
    """
    redactor = _get_redactor()

    if isinstance(value, str):
        return redactor.redact(value)
    elif isinstance(value, dict):
        return {k: sanitize_log_value(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return type(value)(sanitize_log_value(v) for v in value)
    else:
        return value


def secret_sanitizer(
    logger: logging.Logger,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Structlog processor to sanitize secrets from log entries.

    This processor runs on every log entry and removes any detected
    secrets before they're output.

    Args:
        logger: Logger instance (unused)
        method_name: Log method name (unused)
        event_dict: Event dictionary to process

    Returns:
        Sanitized event dictionary
    """
    result = sanitize_log_value(event_dict)
    # Cast is safe - sanitize_log_value returns same type for MutableMapping
    return cast(MutableMapping[str, Any], result)


def add_context_processor(
    logger: logging.Logger,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Add contextual information to all log entries.

    Adds standard fields for correlation and debugging:
    - service: Always "ai-issue-agent"
    - version: Current application version (if available)

    Args:
        logger: Logger instance (unused)
        method_name: Log method name (unused)
        event_dict: Event dictionary to process

    Returns:
        Event dictionary with added context
    """
    event_dict["service"] = "ai-issue-agent"

    # Try to add version
    try:
        from ai_issue_agent._version import __version__

        event_dict["version"] = __version__
    except ImportError:
        pass

    return event_dict


def configure_logging(
    level: LogLevel | str = LogLevel.INFO,
    log_format: LogFormat | str = LogFormat.JSON,
    file_path: Path | str | None = None,
    file_enabled: bool = False,
) -> None:
    """Configure structured logging for the application.

    This function sets up structlog with:
    - Appropriate processors for the output format
    - Secret sanitization
    - Context injection
    - Optional file output

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format (json or console)
        file_path: Path to log file (if file logging enabled)
        file_enabled: Whether to enable file logging

    Example:
        # For development (colored console output)
        configure_logging(level="DEBUG", log_format="console")

        # For production (JSON for log aggregation)
        configure_logging(level="INFO", log_format="json")
    """
    # Convert string values to enums
    if isinstance(level, str):
        level = LogLevel(level.upper())
    if isinstance(log_format, str):
        log_format = LogFormat(log_format.lower())

    # Get numeric log level
    numeric_level = getattr(logging, level.value)

    # Build processor chain
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        add_context_processor,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        secret_sanitizer,  # Always sanitize secrets
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Add format-specific renderer
    if log_format == LogFormat.JSON:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True, exception_formatter=structlog.dev.plain_traceback
            )
        )

    # Configure structlog
    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    handlers: list[logging.Handler] = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    handlers.append(console_handler)

    # File handler (if enabled)
    if file_enabled and file_path:
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(file_path)
            file_handler.setLevel(numeric_level)
            handlers.append(file_handler)
        except OSError as e:
            # Log warning but don't fail - continue with console only
            console_logger = logging.getLogger("ai_issue_agent.logging")
            console_logger.warning(f"Could not create log file {file_path}: {e}")

    # Apply configuration
    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        handlers=handlers,
        force=True,
    )


def get_logger(name: str | None = None) -> WrappedLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (defaults to caller's module)

    Returns:
        Configured structlog logger
    """
    return cast(WrappedLogger, structlog.get_logger(name))


def bind_context(**kwargs: Any) -> None:
    """Bind contextual variables for all subsequent log calls.

    These values will be included in all log entries until cleared.

    Args:
        **kwargs: Key-value pairs to bind

    Example:
        bind_context(channel_id="C123", user_id="U456")
        log.info("processing_message")  # Includes channel_id and user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Remove contextual variables.

    Args:
        *keys: Keys to unbind
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all bound contextual variables."""
    structlog.contextvars.clear_contextvars()


class LogEventNames:
    """Standard log event names for consistency.

    Use these constants to ensure consistent event naming across
    the codebase, making log aggregation and alerting easier.
    """

    # Agent lifecycle
    AGENT_STARTING = "agent_starting"
    AGENT_STARTED = "agent_started"
    AGENT_STOPPING = "agent_stopping"
    AGENT_STOPPED = "agent_stopped"
    AGENT_ERROR = "agent_error"

    # Message processing
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_PROCESSING = "message_processing"
    MESSAGE_PROCESSED = "message_processed"
    MESSAGE_ERROR = "message_error"

    # Traceback detection
    TRACEBACK_DETECTED = "traceback_detected"
    TRACEBACK_NOT_FOUND = "traceback_not_found"
    TRACEBACK_PARSED = "traceback_parsed"
    TRACEBACK_PARSE_ERROR = "traceback_parse_error"

    # Issue matching
    ISSUE_SEARCH_START = "issue_search_start"
    ISSUE_SEARCH_COMPLETE = "issue_search_complete"
    ISSUE_MATCHED = "issue_matched"
    ISSUE_NO_MATCH = "issue_no_match"
    ISSUE_MATCH_ERROR = "issue_match_error"

    # Issue creation
    ISSUE_CREATING = "issue_creating"
    ISSUE_CREATED = "issue_created"
    ISSUE_CREATE_ERROR = "issue_create_error"

    # LLM operations
    LLM_REQUEST_START = "llm_request_start"
    LLM_REQUEST_COMPLETE = "llm_request_complete"
    LLM_REQUEST_ERROR = "llm_request_error"

    # Security events
    SENSITIVE_DATA_REDACTED = "sensitive_data_redacted"
    SECURITY_VIOLATION = "security_violation"
    INPUT_REJECTED = "input_rejected"

    # Rate limiting
    RATE_LIMIT_HIT = "rate_limit_hit"
    RATE_LIMIT_RETRY = "rate_limit_retry"

    # Health checks
    HEALTH_CHECK_START = "health_check_start"
    HEALTH_CHECK_COMPLETE = "health_check_complete"
    HEALTH_CHECK_FAILED = "health_check_failed"

    # Cache operations
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    CACHE_EXPIRED = "cache_expired"

    # Connection events
    CHAT_CONNECTED = "chat_connected"
    CHAT_DISCONNECTED = "chat_disconnected"
    CHAT_CONNECTION_ERROR = "chat_connection_error"
    VCS_CONNECTED = "vcs_connected"
    VCS_CONNECTION_ERROR = "vcs_connection_error"
