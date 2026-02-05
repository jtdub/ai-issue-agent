"""Utility functions and helpers.

This module provides various utilities for the AI Issue Agent:
- security: Secret redaction, input validation
- safe_subprocess: Safe subprocess execution
- async_helpers: Async retry, rate limiting
- logging: Structured logging with secret sanitization
- health: Health check utilities
- metrics: Application metrics collection
"""

from ai_issue_agent.utils.health import (
    HealthChecker,
    HealthReport,
    HealthStatus,
)
from ai_issue_agent.utils.logging import (
    LogConfig,
    LogFormat,
    LogLevel,
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    unbind_context,
)
from ai_issue_agent.utils.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    Timer,
    get_metrics,
)
from ai_issue_agent.utils.security import (
    RedactionError,
    SecretRedactor,
    SecurityError,
    ValidationError,
)

__all__ = [
    # Metrics
    "Counter",
    "Gauge",
    # Health
    "HealthChecker",
    "HealthReport",
    "HealthStatus",
    "Histogram",
    # Logging
    "LogConfig",
    "LogFormat",
    "LogLevel",
    "MetricsRegistry",
    # Security
    "RedactionError",
    "SecretRedactor",
    "SecurityError",
    "Timer",
    "ValidationError",
    "bind_context",
    "clear_context",
    "configure_logging",
    "get_logger",
    "get_metrics",
    "unbind_context",
]
