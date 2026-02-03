# API Reference

API documentation for AI Issue Agent modules.

## Overview

The AI Issue Agent is organized into the following modules:

- **Core**: Message processing, traceback parsing, issue matching
- **Adapters**: Platform integrations (Slack, GitHub, LLMs)
- **Interfaces**: Abstract protocols for adapters
- **Models**: Data structures for tracebacks, issues, and messages
- **Utils**: Security, subprocess handling, async helpers
- **Config**: Configuration management

## Implemented Modules

### Security Module

The security module provides utilities for handling sensitive data safely.

**Key Classes:**
- `SecretRedactor`: Redacts sensitive information from text using 30+ regex patterns
  - API keys (OpenAI, Anthropic, Google, etc.)
  - GitHub tokens
  - Slack tokens
  - Database credentials
  - Private keys
  - Email addresses

**Example:**
```python
from ai_issue_agent.utils.security import SecretRedactor

redactor = SecretRedactor()
safe_text = redactor.redact("My key is sk-abc123")
# Output: "My key is [REDACTED]"
```

### Safe Subprocess Module

Provides secure wrappers for external commands (primarily GitHub CLI).

**Key Classes:**
- `SafeGHCli`: Safe wrapper for GitHub CLI commands
  - Input validation
  - Output sanitization
  - Secret redaction
  - Command allowlisting

**Example:**
```python
from ai_issue_agent.utils.safe_subprocess import SafeGHCli

gh = SafeGHCli()
result = gh.create_issue(
    repo="owner/repo",
    title="Bug report",
    body="Description"
)
```

### Async Helpers Module

Utilities for asynchronous operations.

**Key Functions:**
- `retry_async()`: Retry async operations with exponential backoff
- `RateLimiter`: Token bucket rate limiter for API calls
- `timeout()`: Timeout wrapper for async operations

**Example:**
```python
from ai_issue_agent.utils.async_helpers import retry_async, RateLimiter

@retry_async(max_attempts=3, backoff_factor=2.0)
async def fetch_data():
    # Will retry up to 3 times on failure
    return await api_call()

limiter = RateLimiter(requests_per_second=10)
async with limiter:
    await make_api_call()
```

## Module Structure

```
ai_issue_agent/
├── core/              # Core processing logic (TBD)
├── adapters/          # Platform integrations (TBD)
│   ├── chat/         # Slack, Discord, etc.
│   ├── vcs/          # GitHub, GitLab, etc.
│   └── llm/          # OpenAI, Anthropic, Ollama
├── interfaces/        # Abstract protocols (TBD)
├── models/            # Data models (TBD)
├── utils/             # Utilities (implemented)
│   ├── security.py
│   ├── safe_subprocess.py
│   └── async_helpers.py
└── config/            # Configuration (TBD)
```

## Protocols (Planned)

### ChatProvider

```python
class ChatProvider(Protocol):
    async def connect(self) -> None: ...
    async def listen(self) -> AsyncIterator[Message]: ...
    async def send_message(self, channel: str, text: str) -> str: ...
```

### VCSProvider

```python
class VCSProvider(Protocol):
    async def create_issue(self, repo: str, issue: Issue) -> IssueResult: ...
    async def search_issues(self, repo: str, query: str) -> List[Issue]: ...
    async def add_comment(self, issue_url: str, comment: str) -> None: ...
```

### LLMProvider

```python
class LLMProvider(Protocol):
    async def analyze_traceback(self, traceback: str) -> Analysis: ...
    async def suggest_fix(self, traceback: str, context: str) -> str: ...
```

## Full API Documentation

Full API documentation with all methods, parameters, and examples will be available once the core modules are implemented.

To generate API docs from code:

```bash
# Install with docs dependencies
pip install -e ".[docs]"

# Build and serve documentation
mkdocs serve

# Build static site
mkdocs build
```

The API reference will be automatically generated from docstrings using `mkdocstrings[python]`.

## See Also

- [Architecture Documentation](architecture.md) - System design and component interaction
- [Development Setup](setup.md) - Setting up development environment
- [Testing Guide](testing.md) - Writing and running tests
- [Contributing Guide](contributing.md) - Contribution guidelines
