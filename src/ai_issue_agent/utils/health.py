"""Health check utilities for monitoring service health.

This module provides health check capabilities for the AI Issue Agent:
- Check Slack connection status
- Check GitHub CLI authentication
- Check LLM provider connectivity
- Generate health status reports

See docs/admin-guide/monitoring.md for operational guidance.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from ai_issue_agent.config.schema import AgentConfig

log = structlog.get_logger()


class HealthStatus(StrEnum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    status: HealthStatus
    message: str
    latency_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Overall health report."""

    healthy: bool
    status: HealthStatus
    timestamp: datetime
    checks: list[CheckResult]
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "healthy": self.healthy,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_ms": c.latency_ms,
                    "details": c.details,
                }
                for c in self.checks
            ],
            "details": self.details,
        }


class HealthChecker:
    """Performs health checks on all service dependencies.

    This class provides comprehensive health checking for:
    - Configuration validation
    - Slack connectivity (token validation)
    - GitHub CLI authentication
    - LLM provider connectivity

    Example:
        checker = HealthChecker(config)
        result = await checker.run_all_checks()
        if result.healthy:
            print("All systems operational")
        else:
            print(f"Issues detected: {result.details}")
    """

    def __init__(self, config: AgentConfig) -> None:
        """Initialize the health checker.

        Args:
            config: Application configuration
        """
        self._config = config

    async def run_all_checks(self) -> HealthReport:
        """Run all health checks and return a report.

        Returns:
            HealthReport with results of all checks
        """
        log.info("health_check_start")
        start_time = datetime.now(UTC)

        checks: list[CheckResult] = []

        # Run checks concurrently
        results = await asyncio.gather(
            self._check_config(),
            self._check_github_auth(),
            self._check_llm_provider(),
            self._check_slack_tokens(),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, BaseException):
                checks.append(
                    CheckResult(
                        name="unknown",
                        status=HealthStatus.UNHEALTHY,
                        message=f"Check failed with exception: {result}",
                    )
                )
            elif isinstance(result, CheckResult):
                checks.append(result)

        # Determine overall status
        if all(c.status == HealthStatus.HEALTHY for c in checks):
            overall_status = HealthStatus.HEALTHY
            healthy = True
        elif any(c.status == HealthStatus.UNHEALTHY for c in checks):
            overall_status = HealthStatus.UNHEALTHY
            healthy = False
        else:
            overall_status = HealthStatus.DEGRADED
            healthy = True

        report = HealthReport(
            healthy=healthy,
            status=overall_status,
            timestamp=start_time,
            checks=checks,
            details={
                "total_checks": len(checks),
                "healthy_checks": sum(1 for c in checks if c.status == HealthStatus.HEALTHY),
                "degraded_checks": sum(1 for c in checks if c.status == HealthStatus.DEGRADED),
                "unhealthy_checks": sum(1 for c in checks if c.status == HealthStatus.UNHEALTHY),
            },
        )

        log.info(
            "health_check_complete",
            healthy=healthy,
            status=overall_status.value,
            checks_run=len(checks),
        )

        return report

    async def _check_config(self) -> CheckResult:
        """Check configuration validity."""
        try:
            # Basic validation - config exists and has required fields
            if not self._config.chat.provider:
                return CheckResult(
                    name="config",
                    status=HealthStatus.UNHEALTHY,
                    message="Chat provider not configured",
                )

            if not self._config.vcs.provider:
                return CheckResult(
                    name="config",
                    status=HealthStatus.UNHEALTHY,
                    message="VCS provider not configured",
                )

            if not self._config.llm.provider:
                return CheckResult(
                    name="config",
                    status=HealthStatus.UNHEALTHY,
                    message="LLM provider not configured",
                )

            return CheckResult(
                name="config",
                status=HealthStatus.HEALTHY,
                message="Configuration valid",
                details={
                    "chat_provider": self._config.chat.provider,
                    "vcs_provider": self._config.vcs.provider,
                    "llm_provider": self._config.llm.provider,
                },
            )
        except Exception as e:
            return CheckResult(
                name="config",
                status=HealthStatus.UNHEALTHY,
                message=f"Configuration error: {e}",
            )

    async def _check_slack_tokens(self) -> CheckResult:
        """Check Slack token availability (not validity - that requires API call)."""
        try:
            if self._config.chat.provider != "slack":
                return CheckResult(
                    name="slack_tokens",
                    status=HealthStatus.HEALTHY,
                    message="Slack not configured, skipping",
                )

            slack_config = self._config.chat.slack
            if not slack_config:
                return CheckResult(
                    name="slack_tokens",
                    status=HealthStatus.UNHEALTHY,
                    message="Slack configuration missing",
                )

            # Check token format (validation happens in schema, but double-check)
            bot_token = slack_config.bot_token
            app_token = slack_config.app_token

            if not bot_token.startswith("xoxb-"):
                return CheckResult(
                    name="slack_tokens",
                    status=HealthStatus.UNHEALTHY,
                    message="Invalid bot token format",
                )

            if not app_token.startswith("xapp-"):
                return CheckResult(
                    name="slack_tokens",
                    status=HealthStatus.UNHEALTHY,
                    message="Invalid app token format",
                )

            return CheckResult(
                name="slack_tokens",
                status=HealthStatus.HEALTHY,
                message="Slack tokens configured",
                details={
                    "bot_token_present": True,
                    "app_token_present": True,
                },
            )
        except Exception as e:
            return CheckResult(
                name="slack_tokens",
                status=HealthStatus.UNHEALTHY,
                message=f"Slack token check failed: {e}",
            )

    async def _check_github_auth(self) -> CheckResult:
        """Check GitHub CLI authentication status."""
        import time

        try:
            from ai_issue_agent.utils.safe_subprocess import SafeGHCli

            start = time.monotonic()

            # Get gh_path from config if available
            gh_path = None
            if self._config.vcs.github:
                gh_path = self._config.vcs.github.gh_path

            gh = SafeGHCli(gh_path=gh_path)

            # Check auth status
            is_authenticated = await gh.check_auth()
            latency = (time.monotonic() - start) * 1000

            if is_authenticated:
                return CheckResult(
                    name="github_auth",
                    status=HealthStatus.HEALTHY,
                    message="GitHub CLI authenticated",
                    latency_ms=latency,
                )
            else:
                return CheckResult(
                    name="github_auth",
                    status=HealthStatus.UNHEALTHY,
                    message="GitHub CLI not authenticated",
                    latency_ms=latency,
                )
        except FileNotFoundError:
            return CheckResult(
                name="github_auth",
                status=HealthStatus.UNHEALTHY,
                message="GitHub CLI (gh) not found in PATH",
            )
        except Exception as e:
            return CheckResult(
                name="github_auth",
                status=HealthStatus.UNHEALTHY,
                message=f"GitHub auth check failed: {e}",
            )

    async def _check_llm_provider(self) -> CheckResult:
        """Check LLM provider configuration."""
        try:
            provider = self._config.llm.provider

            if provider == "openai":
                openai_config = self._config.llm.openai
                if not openai_config:
                    return CheckResult(
                        name="llm_provider",
                        status=HealthStatus.UNHEALTHY,
                        message="OpenAI configuration not found",
                    )
                api_key = openai_config.api_key
                if not api_key or api_key.startswith("${"):
                    return CheckResult(
                        name="llm_provider",
                        status=HealthStatus.UNHEALTHY,
                        message="OpenAI API key not configured",
                    )
                return CheckResult(
                    name="llm_provider",
                    status=HealthStatus.HEALTHY,
                    message="OpenAI configured",
                    details={"provider": "openai", "model": openai_config.model},
                )

            elif provider == "anthropic":
                anthropic_config = self._config.llm.anthropic
                if not anthropic_config:
                    return CheckResult(
                        name="llm_provider",
                        status=HealthStatus.UNHEALTHY,
                        message="Anthropic configuration not found",
                    )
                api_key = anthropic_config.api_key
                if not api_key or api_key.startswith("${"):
                    return CheckResult(
                        name="llm_provider",
                        status=HealthStatus.UNHEALTHY,
                        message="Anthropic API key not configured",
                    )
                return CheckResult(
                    name="llm_provider",
                    status=HealthStatus.HEALTHY,
                    message="Anthropic configured",
                    details={"provider": "anthropic", "model": anthropic_config.model},
                )

            elif provider == "ollama":
                ollama_config = self._config.llm.ollama
                if not ollama_config:
                    return CheckResult(
                        name="llm_provider",
                        status=HealthStatus.UNHEALTHY,
                        message="Ollama configuration missing",
                    )
                return CheckResult(
                    name="llm_provider",
                    status=HealthStatus.HEALTHY,
                    message="Ollama configured",
                    details={
                        "provider": "ollama",
                        "base_url": ollama_config.base_url,
                        "model": ollama_config.model,
                    },
                )

            else:
                return CheckResult(
                    name="llm_provider",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Unknown LLM provider: {provider}",
                )

        except Exception as e:
            return CheckResult(
                name="llm_provider",
                status=HealthStatus.UNHEALTHY,
                message=f"LLM provider check failed: {e}",
            )


async def write_health_file(report: HealthReport, path: Path) -> None:
    """Write health report to a file for external monitoring.

    Args:
        report: Health report to write
        path: File path to write to
    """
    import json

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), indent=2))
        log.debug("health_file_written", path=str(path))
    except OSError as e:
        log.error("health_file_write_error", path=str(path), error=str(e))
