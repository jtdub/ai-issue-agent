"""Shared test fixtures for AI Issue Agent."""

from pathlib import Path

import pytest

# Get the fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TRACEBACKS_DIR = FIXTURES_DIR / "tracebacks"
ISSUES_DIR = FIXTURES_DIR / "issues"
SECURITY_DIR = FIXTURES_DIR / "security"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def sample_traceback() -> str:
    """Load a simple sample traceback."""
    return (TRACEBACKS_DIR / "simple.txt").read_text()


@pytest.fixture
def nested_traceback() -> str:
    """Load a nested/chained exception traceback."""
    return (TRACEBACKS_DIR / "nested.txt").read_text()


@pytest.fixture
def traceback_with_secrets() -> str:
    """Load a traceback containing secrets for redaction testing."""
    return (TRACEBACKS_DIR / "with_secrets.txt").read_text()


@pytest.fixture
def syntax_error_traceback() -> str:
    """Load a SyntaxError traceback."""
    return (TRACEBACKS_DIR / "syntax_error.txt").read_text()


@pytest.fixture
def multiline_msg_traceback() -> str:
    """Load a traceback with multi-line exception message."""
    return (TRACEBACKS_DIR / "multiline_msg.txt").read_text()


@pytest.fixture
def code_block_traceback() -> str:
    """Load a traceback embedded in a markdown code block."""
    return (TRACEBACKS_DIR / "in_code_block.txt").read_text()


@pytest.fixture
def truncated_traceback() -> str:
    """Load a truncated traceback missing the header."""
    return (TRACEBACKS_DIR / "truncated.txt").read_text()


@pytest.fixture
def known_secrets() -> list[tuple[str, str]]:
    """Return a list of (secret, pattern_name) tuples for testing."""
    return [
        ("sk-FAKEabcd1234abcd1234abcd1234abcd1234abcd1234abcd", "OpenAI legacy"),
        ("sk-proj-FAKEnotreal0123456789", "OpenAI project"),
        ("ghp_FAKEnotreal1234567890123456789012", "GitHub PAT"),
        ("github_pat_FAKEnotreal01234567890123", "GitHub fine-grained PAT"),
        ("xoxb" + "-1234567890-1234567890-FAKEnotreal0123456789", "Slack bot token"),
        ("xapp-1-A0123456789-1234567890123-FAKEnotreal012", "Slack app token"),
        ("sk-ant-FAKEnotreal0123456789012345678901234567", "Anthropic"),
        ("AKIAFAKENOTREAL12345", "AWS access key"),
        ("postgresql://testuser:testpass@localhost:5432/testdb", "Database URL"),
        ("-----BEGIN PRIVATE KEY-----", "Private key"),
        (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJGQUtFVEVTVCJ9.dBjftJeZ4CVPmB92K27uhbDJU_u0HfzXGzNNFjz0zFc",
            "JWT",
        ),
    ]


@pytest.fixture
def malicious_repo_names() -> list[str]:
    """Return a list of malicious repository names for testing."""
    return [
        "owner/repo; rm -rf /",
        "owner/repo$(whoami)",
        "owner/repo`id`",
        "../../../etc/passwd",
        "owner/repo\nmalicious",
        "owner/repo|cat /etc/passwd",
        "owner/repo&& echo pwned",
        "owner/repo\x00null",
    ]


@pytest.fixture
def valid_repo_names() -> list[str]:
    """Return a list of valid repository names for testing."""
    return [
        "owner/repo",
        "my-org/my-project",
        "user123/repo_name",
        "Org.Name/Repo.Name",
        "a/b",
    ]
