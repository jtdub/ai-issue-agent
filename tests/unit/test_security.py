"""Tests for security utilities.

These tests verify that:
1. All secret patterns from SECURITY.md are detected
2. Redaction fails closed (blocks on error)
3. Malicious repo names are rejected
4. Non-localhost Ollama URLs are rejected by default
"""

from __future__ import annotations

import pytest

from ai_issue_agent.utils.security import (
    RedactionError,
    SecretRedactor,
    mask_config_value,
    redact_file_paths,
    sanitize_for_logging,
    sanitize_for_shell,
    validate_ollama_url,
    validate_repo_name,
)


class TestSecretRedactor:
    """Test secret redaction patterns - see SECURITY.md for canonical list."""

    @pytest.mark.parametrize(
        "secret,name",
        [
            # OpenAI
            ("sk-FAKEabcd1234abcd1234abcd1234abcd1234abcd1234abcd", "OpenAI legacy"),
            ("sk-proj-FAKEnotreal0123456789", "OpenAI project"),
            # GitHub
            ("ghp_FAKEnotreal0123456789012345678901234", "GitHub PAT"),
            ("github_pat_FAKEnotreal01234567890123", "GitHub fine-grained PAT"),
            ("gho_FAKEnotreal0123456789012345678901234", "GitHub OAuth"),
            ("ghu_FAKEnotreal0123456789012345678901234", "GitHub user-to-server"),
            ("ghs_FAKEnotreal0123456789012345678901234", "GitHub server-to-server"),
            ("ghr_FAKEnotreal0123456789012345678901234", "GitHub refresh"),
            # Slack  
            ("xoxb" + "-1234567890-1234567890-FAKEnotreal0123456789", "Slack bot"),
            ("xoxp" + "-1234567890-1234567890-FAKEnotreal0123456789", "Slack user"),
            ("xoxa" + "-1234567890-1234567890-FAKEnotreal0123456789", "Slack app"),
            ("xoxr" + "-1234567890-1234567890-FAKEnotreal0123456789", "Slack refresh"),
            # Anthropic
            ("sk-ant-FAKEnotreal01234567890123456789012345678901", "Anthropic"),
            # AWS
            ("AKIAFAKENOTREAL12345", "AWS access key"),
            # Database URLs
            ("postgresql://testuser:testpass@localhost:5432/testdb", "PostgreSQL"),
            ("mysql://testuser:testpass@localhost:3306/testdb", "MySQL"),
            ("mongodb://testuser:testpass@localhost:27017/testdb", "MongoDB"),
            ("mongodb+srv://testuser:testpass@localhost/testdb", "MongoDB SRV"),
            ("redis://testuser:testpass@localhost:6379/0", "Redis"),
            ("amqp://testuser:testpass@localhost:5672/testvhost", "AMQP"),
            # Private keys
            ("-----BEGIN RSA PRIVATE KEY-----", "RSA private key"),
            ("-----BEGIN EC PRIVATE KEY-----", "EC private key"),
            ("-----BEGIN OPENSSH PRIVATE KEY-----", "OpenSSH private key"),
            ("-----BEGIN PGP PRIVATE KEY BLOCK-----", "PGP private key"),
            # JWT
            (
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJGQUtFVEVTVCJ9.dBjftJeZ4CVPmB92K27uhbDJU_u0HfzXGzNNFjz0zFc",
                "JWT",
            ),
            # Stripe
            ("sk_" + "live_FAKEnotreal0123456789012345", "Stripe secret"),
            ("pk_" + "live_FAKEnotreal0123456789012345", "Stripe publishable"),
            ("rk_" + "live_FAKEnotreal0123456789012345", "Stripe restricted"),
            # SendGrid
            (
                "SG." + "FAKEnotreal01234567890.FAKEnotreal01234567890123456789012345678901",
                "SendGrid",
            ),
            # Twilio
            ("SK00000000000000000000000000000000", "Twilio API key"),
            ("AC00000000000000000000000000000000", "Twilio Account SID"),
            # Google
            ("AIzaSyAabcdefghijklmnopqrstuvwxyz123456", "Google API key"),
            ("ya29.abcdefghijklmnopqrstuvwxyz", "Google OAuth"),
            ("GOCSPX-abcdefghij_klmnopqrst", "Google OAuth client secret"),
            # Azure
            (
                "AccountKey=" + "a" * 88,
                "Azure storage",
            ),
            # Generic patterns
            ("api_key=abcd1234567890abcd", "Generic API key"),
            ("password: supersecretpassword123", "Generic password"),
            ("token=abcdefghijklmnop1234", "Generic token"),
            # Private IPs
            ("10.0.0.1", "Private IP 10.x"),
            ("172.16.0.1", "Private IP 172.16.x"),
            ("172.31.255.255", "Private IP 172.31.x"),
            ("192.168.1.1", "Private IP 192.168.x"),
        ],
    )
    def test_redacts_known_secrets(self, secret: str, name: str) -> None:
        """Verify all known secret patterns are detected and redacted."""
        redactor = SecretRedactor()
        text = f"The value is: {secret}"
        result = redactor.redact(text)

        assert secret not in result, f"Failed to redact {name}: {secret}"
        assert "[REDACTED]" in result

    def test_custom_placeholder(self) -> None:
        """Test using a custom placeholder."""
        redactor = SecretRedactor(placeholder="***MASKED***")
        result = redactor.redact("token=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

        assert "ghp_" not in result
        assert "***MASKED***" in result

    def test_custom_patterns(self) -> None:
        """Test adding custom patterns."""
        redactor = SecretRedactor(
            custom_patterns=[
                (r"MYAPP-[A-Z0-9]{16}", "MyApp token"),
            ]
        )

        result = redactor.redact("key=MYAPP-ABCD1234EFGH5678")
        assert "MYAPP-" not in result
        assert "[REDACTED]" in result

    def test_scan_finds_secrets(self) -> None:
        """Test scanning for secrets without redacting."""
        redactor = SecretRedactor()
        text = "API key: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx and more"
        findings = redactor.scan(text)

        assert len(findings) >= 1
        # Check that findings contain pattern name and position
        assert any("GitHub" in f[0] for f in findings)

    def test_has_secrets_true(self) -> None:
        """Test has_secrets returns True when secrets present."""
        redactor = SecretRedactor()
        assert redactor.has_secrets("key=sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890")

    def test_has_secrets_false(self) -> None:
        """Test has_secrets returns False when no secrets."""
        redactor = SecretRedactor()
        assert not redactor.has_secrets("This is just normal text with no secrets")

    def test_empty_text(self) -> None:
        """Test handling of empty text."""
        redactor = SecretRedactor()
        assert redactor.redact("") == ""
        assert redactor.scan("") == []
        assert not redactor.has_secrets("")

    def test_preserves_non_secret_text(self) -> None:
        """Test that non-secret text is preserved."""
        redactor = SecretRedactor()
        text = "Hello, this is a normal message with no secrets."
        assert redactor.redact(text) == text

    def test_multiple_secrets(self) -> None:
        """Test redacting multiple secrets in one text."""
        redactor = SecretRedactor()
        text = """
        OPENAI_KEY=sk-abc123def456ghi789jkl012mno345pqr678stu901vwx234
        GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        DATABASE_URL=postgresql://user:pass@localhost:5432/db
        """
        result = redactor.redact(text)

        assert "sk-" not in result
        assert "ghp_" not in result
        assert "postgresql://" not in result
        assert result.count("[REDACTED]") >= 3


class TestRedactionFailsClosed:
    """Test that redaction fails closed (blocks operation on error)."""

    def test_invalid_custom_pattern_raises(self) -> None:
        """Test that invalid regex patterns raise RedactionError."""
        with pytest.raises(RedactionError):
            SecretRedactor(custom_patterns=[("[invalid(regex", "Bad pattern")])


class TestInputValidation:
    """Test input validation for security."""

    @pytest.mark.parametrize(
        "malicious",
        [
            "owner/repo; rm -rf /",
            "owner/repo$(whoami)",
            "owner/repo`id`",
            "../../../etc/passwd",
            "owner/repo\nmalicious",
            "owner/repo|cat /etc/passwd",
            "owner/repo&& echo pwned",
            "owner/repo\x00null",
            "owner/repo<script>",
            "owner/repo>output",
            "owner/repo{bad}",
            "",
            "just-one-part",
            "too/many/parts",
            "/absolute/path",
        ],
    )
    def test_rejects_malicious_repo_names(self, malicious: str) -> None:
        """Verify malicious repository names are rejected."""
        assert not validate_repo_name(malicious), f"Should reject: {malicious}"

    @pytest.mark.parametrize(
        "valid",
        [
            "owner/repo",
            "my-org/my-project",
            "user123/repo_name",
            "Org.Name/Repo.Name",
            "a/b",
            "CAPS/REPO",
            "num123/456num",
            "with-dash/and_underscore",
            "with.dots/in.name",
        ],
    )
    def test_accepts_valid_repo_names(self, valid: str) -> None:
        """Verify valid repository names are accepted."""
        assert validate_repo_name(valid), f"Should accept: {valid}"


class TestOllamaSSRF:
    """Test SSRF prevention for Ollama URLs."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://169.254.169.254/",  # AWS metadata
            "http://169.254.169.254/latest/meta-data/",
            "http://internal.corp/",
            "http://10.0.0.1:8080/",
            "http://192.168.1.1/",
            "http://admin.internal:11434/",
            "http://[::ffff:169.254.169.254]/",
            "file:///etc/passwd",
            "",
        ],
    )
    def test_rejects_ssrf_attempts(self, url: str) -> None:
        """Verify SSRF attempts are blocked."""
        assert not validate_ollama_url(url), f"Should reject: {url}"

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:11434",
            "http://127.0.0.1:11434",
            "http://localhost:11434/api/generate",
            "https://localhost:11434",
            "http://[::1]:11434",
        ],
    )
    def test_allows_localhost(self, url: str) -> None:
        """Verify localhost URLs are allowed."""
        assert validate_ollama_url(url), f"Should allow: {url}"

    def test_allows_remote_when_enabled(self) -> None:
        """Test that remote hosts are allowed when explicitly enabled."""
        assert validate_ollama_url("http://ollama.example.com:11434", allow_remote=True)

    def test_rejects_remote_by_default(self) -> None:
        """Test that remote hosts are rejected by default."""
        assert not validate_ollama_url("http://ollama.example.com:11434", allow_remote=False)


class TestSanitization:
    """Test sanitization functions."""

    def test_sanitize_for_shell(self) -> None:
        """Test shell metacharacter removal."""
        dangerous = "owner/repo; rm -rf / && echo $HOME"
        result = sanitize_for_shell(dangerous)

        assert ";" not in result
        assert "&" not in result
        assert "$" not in result

    def test_sanitize_for_shell_preserves_safe_chars(self) -> None:
        """Test that safe characters are preserved."""
        safe = "my-org/my_project.name"
        assert sanitize_for_shell(safe) == safe

    def test_sanitize_for_logging_removes_ansi(self) -> None:
        """Test ANSI escape code removal."""
        text = "\x1b[31mRed text\x1b[0m and \x1b[1;32mgreen\x1b[0m"
        result = sanitize_for_logging(text)

        assert "\x1b[" not in result
        assert "Red text" in result

    def test_sanitize_for_logging_removes_control_chars(self) -> None:
        """Test control character removal."""
        text = "Normal\x00null\x08backspace\x7fdelete"
        result = sanitize_for_logging(text)

        assert "\x00" not in result
        assert "\x08" not in result
        assert "\x7f" not in result
        assert "Normal" in result

    def test_sanitize_for_logging_preserves_newlines(self) -> None:
        """Test that newlines and tabs are preserved."""
        text = "Line 1\nLine 2\tTabbed"
        result = sanitize_for_logging(text)

        assert "\n" in result
        assert "\t" in result


class TestFilePathRedaction:
    """Test file path redaction."""

    def test_redacts_home_paths(self) -> None:
        """Test redaction of home directory paths."""
        text = "Error in /home/jsmith/project/src/main.py"
        result = redact_file_paths(text)

        assert "/home/jsmith/" not in result

    def test_redacts_users_paths(self) -> None:
        """Test redaction of macOS user paths."""
        text = "Error in /Users/johndoe/code/app/main.py"
        result = redact_file_paths(text)

        assert "/Users/johndoe/" not in result

    def test_preserves_relative_paths(self) -> None:
        """Test that relative paths are preserved."""
        text = "Error in src/main.py at line 42"
        result = redact_file_paths(text)

        assert "src/main.py" in result


class TestMaskConfigValue:
    """Test config value masking."""

    @pytest.mark.parametrize(
        "key",
        [
            "api_key",
            "API_KEY",
            "secret",
            "SECRET_KEY",
            "password",
            "PASSWORD",
            "token",
            "access_token",
            "credential",
        ],
    )
    def test_masks_sensitive_keys(self, key: str) -> None:
        """Test that sensitive config keys are masked."""
        value = "supersecretvalue123"
        result = mask_config_value(key, value)

        assert result != value
        assert "..." in result

    def test_preserves_non_sensitive_keys(self) -> None:
        """Test that non-sensitive keys are not masked."""
        assert mask_config_value("host", "localhost") == "localhost"
        assert mask_config_value("port", "5432") == "5432"
        assert mask_config_value("debug", "true") == "true"

    def test_short_values(self) -> None:
        """Test masking of short values."""
        result = mask_config_value("token", "short")
        assert result == "***"
