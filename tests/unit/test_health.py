"""Tests for the health check module."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_issue_agent.utils.health import (
    CheckResult,
    HealthChecker,
    HealthReport,
    HealthStatus,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_values(self) -> None:
        """Test that all expected status values exist."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_create_check_result(self) -> None:
        """Test creating a CheckResult."""
        result = CheckResult(
            name="test_check",
            status=HealthStatus.HEALTHY,
            message="All good",
            latency_ms=50.5,
            details={"key": "value"},
        )
        assert result.name == "test_check"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "All good"
        assert result.latency_ms == 50.5
        assert result.details == {"key": "value"}

    def test_check_result_defaults(self) -> None:
        """Test CheckResult default values."""
        result = CheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            message="OK",
        )
        assert result.latency_ms is None
        assert result.details == {}


class TestHealthReport:
    """Tests for HealthReport dataclass."""

    def test_create_health_report(self) -> None:
        """Test creating a HealthReport."""
        checks = [
            CheckResult(name="check1", status=HealthStatus.HEALTHY, message="OK"),
            CheckResult(name="check2", status=HealthStatus.HEALTHY, message="OK"),
        ]
        report = HealthReport(
            healthy=True,
            status=HealthStatus.HEALTHY,
            timestamp=datetime.now(UTC),
            checks=checks,
        )
        assert report.healthy is True
        assert report.status == HealthStatus.HEALTHY
        assert len(report.checks) == 2

    def test_health_report_to_dict(self) -> None:
        """Test converting HealthReport to dictionary."""
        timestamp = datetime(2026, 2, 4, 12, 0, 0, tzinfo=UTC)
        checks = [
            CheckResult(
                name="config",
                status=HealthStatus.HEALTHY,
                message="Valid",
                latency_ms=10.0,
            ),
        ]
        report = HealthReport(
            healthy=True,
            status=HealthStatus.HEALTHY,
            timestamp=timestamp,
            checks=checks,
            details={"total": 1},
        )

        result = report.to_dict()

        assert result["healthy"] is True
        assert result["status"] == "healthy"
        assert result["timestamp"] == "2026-02-04T12:00:00+00:00"
        assert len(result["checks"]) == 1
        assert result["checks"][0]["name"] == "config"
        assert result["checks"][0]["status"] == "healthy"
        assert result["details"] == {"total": 1}


class TestHealthChecker:
    """Tests for HealthChecker class."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock configuration."""
        config = MagicMock()
        config.chat.provider = "slack"
        config.chat.slack.bot_token = "xoxb-valid-token"
        config.chat.slack.app_token = "xapp-valid-token"
        config.vcs.provider = "github"
        config.vcs.github.gh_path = None
        config.llm.provider = "anthropic"
        config.llm.anthropic.api_key = "sk-ant-valid-key"
        config.llm.anthropic.model = "claude-3-sonnet"
        config.llm.openai = None
        config.llm.ollama = None
        return config

    @pytest.mark.asyncio
    async def test_check_config_valid(self, mock_config: MagicMock) -> None:
        """Test config check with valid configuration."""
        checker = HealthChecker(mock_config)
        result = await checker._check_config()

        assert result.name == "config"
        assert result.status == HealthStatus.HEALTHY
        assert "valid" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_config_missing_chat(self, mock_config: MagicMock) -> None:
        """Test config check with missing chat provider."""
        mock_config.chat.provider = None
        checker = HealthChecker(mock_config)
        result = await checker._check_config()

        assert result.status == HealthStatus.UNHEALTHY
        assert "not configured" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_slack_tokens_valid(self, mock_config: MagicMock) -> None:
        """Test Slack token check with valid tokens."""
        checker = HealthChecker(mock_config)
        result = await checker._check_slack_tokens()

        assert result.name == "slack_tokens"
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_slack_tokens_invalid_bot_token(self, mock_config: MagicMock) -> None:
        """Test Slack token check with invalid bot token."""
        mock_config.chat.slack.bot_token = "invalid-token"
        checker = HealthChecker(mock_config)
        result = await checker._check_slack_tokens()

        assert result.status == HealthStatus.UNHEALTHY
        assert "invalid" in result.message.lower() or "token" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_slack_tokens_skipped(self, mock_config: MagicMock) -> None:
        """Test Slack token check is skipped for non-Slack providers."""
        mock_config.chat.provider = "discord"
        checker = HealthChecker(mock_config)
        result = await checker._check_slack_tokens()

        assert result.status == HealthStatus.HEALTHY
        assert "skipping" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_llm_provider_anthropic(self, mock_config: MagicMock) -> None:
        """Test LLM provider check for Anthropic."""
        checker = HealthChecker(mock_config)
        result = await checker._check_llm_provider()

        assert result.name == "llm_provider"
        assert result.status == HealthStatus.HEALTHY
        assert "anthropic" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_llm_provider_missing_key(self, mock_config: MagicMock) -> None:
        """Test LLM provider check with missing API key."""
        mock_config.llm.anthropic.api_key = "${ANTHROPIC_API_KEY}"  # Unresolved
        checker = HealthChecker(mock_config)
        result = await checker._check_llm_provider()

        assert result.status == HealthStatus.UNHEALTHY
        assert "not configured" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_github_auth_success(self, mock_config: MagicMock) -> None:
        """Test GitHub auth check with successful auth."""
        checker = HealthChecker(mock_config)

        with patch("ai_issue_agent.utils.safe_subprocess.SafeGHCli") as mock_gh_class:
            mock_gh = MagicMock()
            mock_gh.check_auth = AsyncMock(return_value=True)
            mock_gh_class.return_value = mock_gh

            result = await checker._check_github_auth()

        assert result.name == "github_auth"
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_github_auth_failure(self, mock_config: MagicMock) -> None:
        """Test GitHub auth check with auth failure."""
        checker = HealthChecker(mock_config)

        with patch("ai_issue_agent.utils.safe_subprocess.SafeGHCli") as mock_gh_class:
            mock_gh = MagicMock()
            mock_gh.check_auth = AsyncMock(return_value=False)
            mock_gh_class.return_value = mock_gh

            result = await checker._check_github_auth()

        assert result.status == HealthStatus.UNHEALTHY
        assert "not authenticated" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_github_auth_gh_not_found(self, mock_config: MagicMock) -> None:
        """Test GitHub auth check when gh CLI is not found."""
        checker = HealthChecker(mock_config)

        with patch("ai_issue_agent.utils.safe_subprocess.SafeGHCli") as mock_gh_class:
            mock_gh_class.side_effect = FileNotFoundError("gh not found")

            result = await checker._check_github_auth()

        assert result.status == HealthStatus.UNHEALTHY
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_run_all_checks_healthy(self, mock_config: MagicMock) -> None:
        """Test run_all_checks with all healthy checks."""
        checker = HealthChecker(mock_config)

        with patch("ai_issue_agent.utils.safe_subprocess.SafeGHCli") as mock_gh_class:
            mock_gh = MagicMock()
            mock_gh.check_auth = AsyncMock(return_value=True)
            mock_gh_class.return_value = mock_gh

            report = await checker.run_all_checks()

        assert report.healthy is True
        assert report.status == HealthStatus.HEALTHY
        assert len(report.checks) == 4

    @pytest.mark.asyncio
    async def test_run_all_checks_with_failure(self, mock_config: MagicMock) -> None:
        """Test run_all_checks with one failing check."""
        mock_config.llm.anthropic.api_key = "${MISSING}"  # Will fail
        checker = HealthChecker(mock_config)

        with patch("ai_issue_agent.utils.safe_subprocess.SafeGHCli") as mock_gh_class:
            mock_gh = MagicMock()
            mock_gh.check_auth = AsyncMock(return_value=True)
            mock_gh_class.return_value = mock_gh

            report = await checker.run_all_checks()

        assert report.healthy is False
        assert report.status == HealthStatus.UNHEALTHY
        assert report.details["unhealthy_checks"] > 0
