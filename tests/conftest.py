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
def known_secrets() -> list[tuple[str, str]]:
    """Return a list of (secret, pattern_name) tuples for testing."""
    return [
        ("sk_test_FakeKey1234567890NotRealDoNotUse123456789", "OpenAI legacy"),
        ("sk-proj-FAKEtestkey1234567890", "OpenAI project"),
        ("ghp_FakeToken1234567890NotRealTestOnly12345", "GitHub PAT"),
        ("github_pat_FAKETEST1234567890", "GitHub fine-grained PAT"),
        ("xoxb-TEST-FAKE-TOKEN-NotARealSlackToken12345", "Slack bot token"),
        ("xapp-TEST-FAKE-APP-TOKEN-NotReal", "Slack app token"),
        ("sk-ant-FAKETEST-notarealkeyjustfortesting", "Anthropic"),
        ("FAKEEXAMPLEKEYNOTREAL", "AWS access key"),
        ("postgresql://testuser:testpass@localhost:5432/testdb", "Database URL"),
        ("-----BEGIN FAKE PRIVATE KEY-----", "Private key"),
        (
            "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJGQUtFVEVTVCJ9.FAKE_SIGNATURE",
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
