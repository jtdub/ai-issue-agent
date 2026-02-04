# Testing Guide

Comprehensive testing guide for AI Issue Agent.

## Test Structure

```
tests/
├── unit/              # Unit tests
├── integration/       # Integration tests
├── e2e/               # End-to-end tests
├── fixtures/          # Test data
└── conftest.py        # Shared fixtures
```

## Running Tests

```bash
# All tests
poetry run pytest

# Unit tests only
poetry run pytest tests/unit

# Specific test file
poetry run pytest tests/unit/test_security.py

# Specific test
poetry run pytest tests/unit/test_security.py::TestSecretRedactor::test_redacts_known_secrets

# With coverage
poetry run pytest --cov=src/ai_issue_agent --cov-report=html

# Verbose output
poetry run pytest -v

# Stop on first failure
poetry run pytest -x

# Run only failed tests
poetry run pytest --lf

# Skip slow/integration tests
poetry run pytest -m "not slow and not integration"
```

## Writing Unit Tests

### Example

```python
import pytest
from ai_issue_agent.utils.security import SecretRedactor

class TestSecretRedactor:
    """Tests for SecretRedactor class."""
    
    def test_redacts_api_keys(self):
        """Test that API keys are redacted."""
        redactor = SecretRedactor()
        text = "My key: sk-abc123"
        
        result = redactor.redact(text)
        
        assert "sk-abc123" not in result
        assert "[REDACTED]" in result
    
    @pytest.mark.parametrize("secret,pattern", [
        ("sk-abc123", "OpenAI"),
        ("ghp_abc123", "GitHub"),
    ])
    def test_redacts_multiple_patterns(self, secret, pattern):
        """Test redaction of multiple secret types."""
        redactor = SecretRedactor()
        
        result = redactor.redact(f"Secret: {secret}")
        
        assert secret not in result
```

## Writing Integration Tests

Test interactions between components:

```python
import pytest
from ai_issue_agent.core.processor import MessageProcessor

@pytest.mark.integration
async def test_message_processing_workflow(mock_slack, mock_github):
    """Test complete message processing workflow."""
    processor = MessageProcessor(config)
    message = create_test_message_with_traceback()
    
    result = await processor.process(message)
    
    assert result.issue_created
    assert result.issue_url.startswith("https://github.com")
```

## Writing E2E Tests

Test the entire system:

```python
@pytest.mark.e2e
@pytest.mark.slow
async def test_slack_to_github_flow(live_slack, live_github):
    """Test end-to-end flow from Slack to GitHub."""
    # Post message to Slack
    message_id = await live_slack.post_message(
        channel="#test",
        text=test_traceback
    )
    
    # Wait for processing
    await asyncio.sleep(10)
    
    # Verify issue created
    issues = await live_github.search_issues("auto-triaged")
    assert any(message_id in issue.body for issue in issues)
```

## Test Fixtures

### Shared Fixtures

```python
# conftest.py
import pytest

@pytest.fixture
def sample_traceback():
    """Sample Python traceback for testing."""
    return """
    Traceback (most recent call last):
      File "test.py", line 10, in main
        result = process()
    ValueError: Invalid input
    """

@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return Config(
        chat=ChatConfig(provider="slack"),
        vcs=VCSConfig(provider="github"),
        llm=LLMConfig(provider="anthropic")
    )
```

## Mocking

### Mock External APIs

```python
import respx
from httpx import Response

@respx.mock
async def test_openai_api_call():
    """Test OpenAI API call with mock response."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": "Analysis result"}}]
        })
    )
    
    provider = OpenAIProvider(api_key="test")
    result = await provider.analyze(traceback)
    
    assert "Analysis result" in result
```

### Mock GitHub CLI

```python
from unittest.mock import patch, MagicMock

def test_github_issue_creation(monkeypatch):
    """Test GitHub issue creation with mocked CLI."""
    mock_run = MagicMock(return_value=CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"url": "https://github.com/org/repo/issues/123"}'
    ))
    
    monkeypatch.setattr("subprocess.run", mock_run)
    
    gh = SafeGHCli()
    result = gh.create_issue("repo", "title", "body")
    
    assert "123" in result.stdout
```

## Test Coverage

### Minimum Requirements

- Overall coverage: 90%+
- New code: 95%+
- Critical paths: 100%

### Generate Coverage Report

```bash
# Terminal report
pytest --cov=src/ai_issue_agent --cov-report=term-missing

# HTML report
pytest --cov=src/ai_issue_agent --cov-report=html
open htmlcov/index.html

# XML report (for CI)
pytest --cov=src/ai_issue_agent --cov-report=xml
```

## Performance Testing

```python
import pytest
import time

@pytest.mark.benchmark
def test_secret_redaction_performance(benchmark):
    """Benchmark secret redaction performance."""
    redactor = SecretRedactor()
    text = "API key: sk-abc123" * 1000
    
    result = benchmark(redactor.redact, text)
    
    assert "sk-abc123" not in result
```

## Test Markers

```python
# Unit test (fast, no external dependencies)
@pytest.mark.unit
def test_function():
    pass

# Integration test (moderate speed, some dependencies)
@pytest.mark.integration
async def test_integration():
    pass

# E2E test (slow, full stack)
@pytest.mark.e2e
@pytest.mark.slow
async def test_e2e():
    pass

# Skip in CI
@pytest.mark.skip_ci
def test_local_only():
    pass
```

Run specific markers:

```bash
pytest -m unit
pytest -m "not slow"
pytest -m "integration or e2e"
```

## Continuous Integration

Tests run automatically on:
- Every pull request
- Every push to main
- Nightly (full test suite including slow tests)

See `.github/workflows/ci.yml` for configuration.

## Best Practices

1. **Test behavior, not implementation**
2. **One assertion per test** (when possible)
3. **Use descriptive test names**
4. **Keep tests fast** (mock external calls)
5. **Clean up after tests** (use fixtures for cleanup)
6. **Test edge cases and errors**
7. **Maintain test data in fixtures/**

## Debugging Failed Tests

```bash
# Run with pdb
pytest --pdb

# Show local variables
pytest -l

# Verbose output
pytest -vv

# Show print statements
pytest -s
```

For more information, see the [Developer Guide](setup.md).
