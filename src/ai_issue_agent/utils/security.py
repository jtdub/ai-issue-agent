"""Security utilities for secret redaction and input validation.

This module implements fail-closed security patterns. All operations that
could potentially leak secrets will fail safely by blocking the operation
rather than proceeding with potentially sensitive data.

See docs/SECURITY.md for the canonical list of secret patterns and security guidelines.
"""

from __future__ import annotations

import ipaddress
import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import structlog

if TYPE_CHECKING:
    from collections.abc import Sequence

log = structlog.get_logger()


class SecurityError(Exception):
    """Base exception for security-related errors."""


class RedactionError(SecurityError):
    """Raised when secret redaction fails."""


class ValidationError(SecurityError):
    """Raised when input validation fails."""


# Repository name validation pattern
REPO_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")

# Shell metacharacters that should never appear in repo names
SHELL_METACHARACTERS = frozenset(
    [";", "|", "&", "`", "$", "(", ")", "{", "}", "<", ">", "\\", "\n", "\r", "\t", "\x00"]
)

# Allowed hosts for Ollama (SSRF prevention)
ALLOWED_OLLAMA_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class SecretRedactor:
    """Detects and redacts secrets from text.

    This class implements fail-closed behavior: if any regex pattern fails to
    compile or execute, it raises an exception rather than allowing potentially
    sensitive data to pass through.

    Usage:
        redactor = SecretRedactor()
        safe_text = redactor.redact(potentially_sensitive_text)

    Attributes:
        patterns: List of compiled regex patterns to detect secrets.
        placeholder: The string to replace secrets with (default: "[REDACTED]").
    """

    # Canonical secret patterns from SECURITY.md
    # DO NOT modify without updating SECURITY.md
    DEFAULT_PATTERNS: tuple[tuple[str, str], ...] = (
        # Generic patterns
        (
            r"(?i)(api[_-]?key|secret|token|password|credential)\s*[=:]\s*[\"']?[\w-]{16,}",
            "Generic secret",
        ),
        # Slack
        (r"xox[baprs]-[\w-]+", "Slack token"),
        # GitHub
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT"),
        (r"github_pat_[a-zA-Z0-9_]{22,}", "GitHub fine-grained PAT"),
        (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth token"),
        (r"ghu_[a-zA-Z0-9]{36}", "GitHub user-to-server token"),
        (r"ghs_[a-zA-Z0-9]{36}", "GitHub server-to-server token"),
        (r"ghr_[a-zA-Z0-9]{36}", "GitHub refresh token"),
        # OpenAI
        (r"sk-[a-zA-Z0-9]{48}", "OpenAI legacy API key"),
        (r"sk-proj-[a-zA-Z0-9]{20,}", "OpenAI project API key"),
        # Anthropic
        (r"sk-ant-[\w-]{40,}", "Anthropic API key"),
        # AWS
        (r"AKIA[0-9A-Z]{16}", "AWS access key ID"),
        (
            r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*[\"']?[a-zA-Z0-9/+=]{40}",
            "AWS secret access key",
        ),
        # Google Cloud
        (r"AIza[0-9A-Za-z\-_]{35}", "Google API key"),
        (r"ya29\.[0-9A-Za-z\-_]+", "Google OAuth access token"),
        (r"GOCSPX-[a-zA-Z0-9_-]+", "Google OAuth client secret"),
        (r'"type"\s*:\s*"service_account"', "Google service account JSON"),
        # Azure
        (r"AccountKey=[a-zA-Z0-9+/=]{88}", "Azure storage account key"),
        (
            r"(?i)azure[_-]?storage[_-]?key\s*[=:]\s*[\"']?[a-zA-Z0-9+/=]+",
            "Azure storage key",
        ),
        # Stripe
        (r"sk_live_[a-zA-Z0-9]{24,}", "Stripe secret key"),
        (r"pk_live_[a-zA-Z0-9]{24,}", "Stripe publishable key"),
        (r"rk_live_[a-zA-Z0-9]{24,}", "Stripe restricted key"),
        # Database connection strings
        (
            r"(?i)(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:]+:[^@]+@[^\s]+",
            "Database connection string",
        ),
        # Private keys
        (
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            "Private key header",
        ),
        (r"-----BEGIN PGP PRIVATE KEY BLOCK-----", "PGP private key"),
        # JWT tokens
        (
            r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
            "JWT token",
        ),
        # SendGrid
        (r"SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}", "SendGrid API key"),
        # Twilio
        (r"SK[a-f0-9]{32}", "Twilio API key"),
        (r"AC[a-f0-9]{32}", "Twilio Account SID"),
        # Internal infrastructure (private IPs)
        (r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "Private IP (10.x.x.x)"),
        (
            r"\b172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b",
            "Private IP (172.16-31.x.x)",
        ),
        (r"\b192\.168\.\d{1,3}\.\d{1,3}\b", "Private IP (192.168.x.x)"),
    )

    def __init__(
        self,
        placeholder: str = "[REDACTED]",
        custom_patterns: Sequence[tuple[str, str]] | None = None,
    ) -> None:
        """Initialize the SecretRedactor.

        Args:
            placeholder: String to replace detected secrets with.
            custom_patterns: Additional (pattern, name) tuples to detect.

        Raises:
            RedactionError: If any pattern fails to compile.
        """
        self.placeholder = placeholder
        self._pattern_names: dict[re.Pattern[str], str] = {}

        all_patterns = list(self.DEFAULT_PATTERNS)
        if custom_patterns:
            all_patterns.extend(custom_patterns)

        # Compile all patterns, fail if any are invalid
        try:
            for pattern_str, name in all_patterns:
                compiled = re.compile(pattern_str)
                self._pattern_names[compiled] = name
        except re.error as e:
            msg = f"Failed to compile secret pattern '{pattern_str}': {e}"
            log.error("pattern_compilation_failed", pattern=pattern_str, error=str(e))
            raise RedactionError(msg) from e

    @property
    def patterns(self) -> list[re.Pattern[str]]:
        """Return the list of compiled patterns."""
        return list(self._pattern_names.keys())

    def redact(self, text: str) -> str:
        """Redact all secrets from the given text.

        This method implements fail-closed behavior: if any pattern matching
        fails, it raises an exception rather than returning potentially
        sensitive data.

        Args:
            text: The text to scan and redact secrets from.

        Returns:
            The text with all detected secrets replaced with placeholder.

        Raises:
            RedactionError: If redaction fails for any reason.
        """
        if not text:
            return text

        try:
            result = text
            for pattern in self._pattern_names:
                result = pattern.sub(self.placeholder, result)
            return result
        except Exception as e:
            msg = f"Redaction failed: {e}"
            log.error("redaction_failed", error=str(e))
            raise RedactionError(msg) from e

    def scan(self, text: str) -> list[tuple[str, str, int, int]]:
        """Scan text for secrets without redacting.

        Args:
            text: The text to scan for secrets.

        Returns:
            List of (pattern_name, matched_text_preview, start, end) tuples.
            The matched_text_preview shows only the first/last few characters.

        Raises:
            RedactionError: If scanning fails for any reason.
        """
        if not text:
            return []

        try:
            findings: list[tuple[str, str, int, int]] = []
            for pattern, name in self._pattern_names.items():
                for match in pattern.finditer(text):
                    # Create a safe preview that doesn't expose the full secret
                    matched = match.group()
                    if len(matched) > 10:
                        preview = f"{matched[:4]}...{matched[-4:]}"
                    else:
                        preview = f"{matched[:2]}..."
                    findings.append((name, preview, match.start(), match.end()))
            return findings
        except Exception as e:
            msg = f"Scanning failed: {e}"
            log.error("scan_failed", error=str(e))
            raise RedactionError(msg) from e

    def has_secrets(self, text: str) -> bool:
        """Check if text contains any secrets.

        Args:
            text: The text to check.

        Returns:
            True if any secrets are detected, False otherwise.

        Raises:
            RedactionError: If checking fails for any reason.
        """
        if not text:
            return False

        try:
            return any(pattern.search(text) for pattern in self._pattern_names)
        except Exception as e:
            msg = f"Secret check failed: {e}"
            log.error("has_secrets_check_failed", error=str(e))
            raise RedactionError(msg) from e


def validate_repo_name(repo: str) -> bool:
    """Validate that a repository name is safe.

    Repository names must match the pattern: owner/repo where both owner
    and repo contain only alphanumeric characters, underscores, hyphens,
    and periods.

    Args:
        repo: The repository name to validate (e.g., "owner/repo").

    Returns:
        True if the repository name is valid, False otherwise.
    """
    if not repo:
        return False

    # Check for shell metacharacters
    if any(char in repo for char in SHELL_METACHARACTERS):
        return False

    # Check against pattern
    return bool(REPO_NAME_PATTERN.match(repo))


def sanitize_for_shell(text: str) -> str:
    """Remove dangerous characters from text intended for shell use.

    This function removes shell metacharacters that could be used for
    command injection. It should be used as a defense-in-depth measure,
    not as a primary security control.

    Args:
        text: The text to sanitize.

    Returns:
        The text with shell metacharacters removed.
    """
    if not text:
        return text

    result = text
    for char in SHELL_METACHARACTERS:
        result = result.replace(char, "")

    return result


def validate_ollama_url(url: str, allow_remote: bool = False) -> bool:
    """Validate that an Ollama URL is safe (SSRF prevention).

    By default, only localhost URLs are allowed. Set allow_remote=True
    to explicitly allow non-localhost URLs.

    Args:
        url: The Ollama base URL to validate.
        allow_remote: If True, allow non-localhost hosts.

    Returns:
        True if the URL is valid and allowed, False otherwise.
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)
        host = parsed.hostname

        if not host:
            return False

        # Check if it's in the allowed hosts
        if host in ALLOWED_OLLAMA_HOSTS:
            return True

        # Check if it's a loopback IP
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_loopback:
                return True
        except ValueError:
            pass  # Not an IP address

        # If remote hosts are allowed, permit it; otherwise reject
        return allow_remote
    except Exception:
        return False


def redact_file_paths(text: str, base_paths: Sequence[str] | None = None) -> str:
    """Strip sensitive path components from file paths.

    Removes absolute path prefixes, keeping only relative project paths.

    Args:
        text: The text containing file paths.
        base_paths: List of path prefixes to remove.

    Returns:
        The text with sensitive path components removed.
    """
    if not text:
        return text

    default_paths = [
        "/home/",
        "/Users/",
        "/root/",
        "/var/",
        "/tmp/",  # noqa: S108 - Not accessing tmp, just stripping from paths
        "/opt/",
    ]

    paths_to_remove = list(base_paths) if base_paths else default_paths

    result = text
    for path in paths_to_remove:
        # Remove paths like /home/username/project/
        pattern = re.compile(rf"{re.escape(path)}[^/\s]+/")
        result = pattern.sub("", result)

    return result


def sanitize_for_logging(text: str) -> str:
    """Remove ANSI escape codes and control characters from text.

    This prevents log injection attacks where malicious content could
    create fake log entries or corrupt terminal output.

    Args:
        text: The text to sanitize.

    Returns:
        The text with ANSI codes and control characters removed.
    """
    if not text:
        return text

    # Remove ANSI escape codes
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)

    # Remove other control characters (except newline, tab, carriage return)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text


def mask_config_value(key: str, value: str) -> str:
    """Mask sensitive config values for logging.

    Args:
        key: The configuration key name.
        value: The configuration value.

    Returns:
        The masked value if the key indicates sensitivity, otherwise the original.
    """
    sensitive_keys = {"token", "key", "secret", "password", "credential", "api_key"}

    key_lower = key.lower()
    if any(s in key_lower for s in sensitive_keys):
        if len(value) > 8:
            return f"{value[:4]}...{value[-4:]}"
        return "***"

    return value
