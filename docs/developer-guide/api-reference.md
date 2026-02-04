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
├── core/              # Core processing logic
│   └── traceback_parser.py  # Python traceback parsing
├── adapters/          # Platform integrations
│   ├── chat/         # Chat platform adapters
│   │   └── slack.py  # Slack via slack-bolt
│   ├── vcs/          # Version control adapters
│   │   └── github.py # GitHub via gh CLI
│   └── llm/          # LLM provider adapters
│       └── anthropic.py  # Anthropic Claude
├── interfaces/        # Abstract protocols
│   ├── chat.py       # ChatProvider protocol
│   ├── vcs.py        # VCSProvider protocol
│   └── llm.py        # LLMProvider protocol
├── models/            # Data models
│   ├── traceback.py  # StackFrame, ParsedTraceback
│   ├── issue.py      # Issue, IssueCreate, IssueMatch
│   ├── message.py    # ChatMessage, ChatReply
│   └── analysis.py   # ErrorAnalysis, SuggestedFix
├── config/            # Configuration
│   ├── schema.py     # Pydantic configuration models
│   └── loader.py     # YAML + env var loading
└── utils/             # Utilities
    ├── security.py       # SecretRedactor, input validation
    ├── safe_subprocess.py  # SafeGHCli wrapper
    └── async_helpers.py  # Retry, rate limiting, timeout
```

## Protocols

### ChatProvider

```python
from typing import Protocol, AsyncIterator
from ai_issue_agent.models.message import ChatMessage

class ChatProvider(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def listen(self) -> AsyncIterator[ChatMessage]: ...
    async def send_reply(
        self, channel_id: str, text: str, 
        thread_id: str | None = None, 
        blocks: list[dict] | None = None
    ) -> str: ...
    async def add_reaction(self, channel_id: str, message_id: str, reaction: str) -> None: ...
    async def remove_reaction(self, channel_id: str, message_id: str, reaction: str) -> None: ...
```

### VCSProvider

```python
from typing import Protocol
from pathlib import Path
from ai_issue_agent.models.issue import Issue, IssueCreate, IssueSearchResult

class VCSProvider(Protocol):
    async def search_issues(self, repo: str, query: str, state: str = "all", max_results: int = 10) -> list[IssueSearchResult]: ...
    async def get_issue(self, repo: str, issue_number: int) -> Issue | None: ...
    async def create_issue(self, repo: str, issue: IssueCreate) -> Issue: ...
    async def clone_repository(self, repo: str, destination: Path, branch: str | None = None, shallow: bool = True) -> Path: ...
    async def get_file_content(self, repo: str, file_path: str, ref: str | None = None) -> str | None: ...
    async def get_default_branch(self, repo: str) -> str: ...
```

### LLMProvider

```python
from typing import Protocol
from ai_issue_agent.models.traceback import ParsedTraceback
from ai_issue_agent.models.analysis import CodeContext, ErrorAnalysis
from ai_issue_agent.models.issue import Issue

class LLMProvider(Protocol):
    async def analyze_error(self, traceback: ParsedTraceback, code_context: list[CodeContext], additional_context: str | None = None) -> ErrorAnalysis: ...
    async def generate_issue_body(self, traceback: ParsedTraceback, analysis: ErrorAnalysis, code_context: list[CodeContext]) -> str: ...
    async def generate_issue_title(self, traceback: ParsedTraceback, analysis: ErrorAnalysis) -> str: ...
    async def calculate_similarity(self, traceback: ParsedTraceback, existing_issues: list[Issue]) -> list[tuple[Issue, float]]: ...
    
    @property
    def model_name(self) -> str: ...
    
    @property
    def max_context_tokens(self) -> int: ...
```

## Data Models

### Traceback Models

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class StackFrame:
    file_path: str
    line_number: int
    function_name: str
    code_line: str | None = None
    
    @property
    def is_stdlib(self) -> bool: ...
    @property
    def is_site_packages(self) -> bool: ...
    @property
    def normalized_path(self) -> str: ...

@dataclass(frozen=True)
class ParsedTraceback:
    exception_type: str
    exception_message: str
    frames: tuple[StackFrame, ...]
    raw_text: str
    is_chained: bool = False
    cause: "ParsedTraceback | None" = None
    
    @property
    def innermost_frame(self) -> StackFrame: ...
    @property
    def project_frames(self) -> tuple[StackFrame, ...]: ...
    @property
    def signature(self) -> str: ...
```

## Full API Documentation

To generate API docs from code:

```bash
# Install with docs dependencies
poetry install --with docs

# Build and serve documentation
poetry run mkdocs serve

# Build static site
poetry run mkdocs build
```

The API reference will be automatically generated from docstrings using `mkdocstrings[python]`.

## See Also

- [Architecture Documentation](architecture.md) - System design and component interaction
- [Development Setup](setup.md) - Setting up development environment
- [Testing Guide](testing.md) - Writing and running tests
- [Contributing Guide](contributing.md) - Contribution guidelines
