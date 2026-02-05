# API Reference

API documentation for AI Issue Agent modules.

## Overview

The AI Issue Agent is organized into the following modules:

- **Core**: Agent orchestrator, message processing, traceback parsing, issue matching, code analysis
- **Adapters**: Platform integrations (Slack, GitHub, Anthropic)
- **Interfaces**: Abstract protocols for adapters
- **Models**: Data structures for tracebacks, issues, messages, and analysis
- **Utils**: Security, subprocess handling, async helpers, logging, health checks, metrics
- **Config**: Configuration management

## Core Modules

### Agent (`core/agent.py`)

The main orchestrator that coordinates all components and manages the application lifecycle.

**Key Classes:**
- `Agent`: Main orchestrator class
  - `start()`: Start listening for messages and processing them
  - `stop()`: Graceful shutdown with in-flight request completion
  - `create_agent(config)`: Factory method to create a fully-configured agent

### MessageHandler (`core/message_handler.py`)

Orchestrates the full message processing pipeline from detection through issue creation.

**Key Classes:**
- `MessageHandler`: Processing pipeline coordinator
  - `handle(message)`: Process a chat message through the full pipeline
  - Coordinates: parsing -> matching -> analysis -> issue creation
  - Manages reactions (eyes -> processing -> checkmark/x)

### TracebackParser (`core/traceback_parser.py`)

Detects and parses Python tracebacks from chat messages.

**Key Classes:**
- `TracebackParser`: Traceback detection and parsing
  - `contains_traceback(text)`: Check if text contains a Python traceback
  - `parse(text)`: Parse text into a `ParsedTraceback` object
  - Handles standard, chained, and syntax error tracebacks

### IssueMatcher (`core/issue_matcher.py`)

Searches for and ranks existing issues by similarity to a new traceback.

**Key Classes:**
- `IssueMatcher`: Issue search and ranking
  - `find_matches(repo, traceback)`: Find existing issues matching a traceback
  - Uses 3 strategies: exact match, similar stack trace, semantic similarity
  - Returns matches ranked by confidence score

### CodeAnalyzer (`core/code_analyzer.py`)

Clones repositories and extracts code context for stack frames.

**Key Classes:**
- `CodeAnalyzer`: Code context extraction
  - `extract_context(repo, traceback)`: Extract code context for a traceback's frames
  - `RepoCache`: TTL-based cache for cloned repositories
  - Path traversal prevention and secret redaction

## Utility Modules

### Security Module (`utils/security.py`)

Utilities for handling sensitive data safely.

**Key Classes:**
- `SecretRedactor`: Redacts sensitive information from text using 30+ regex patterns
  - API keys (OpenAI, Anthropic, Google, etc.)
  - GitHub tokens
  - Slack tokens
  - Database credentials
  - Private keys
  - JWT tokens

**Key Functions:**
- `validate_repo_name(repo)`: Validate repository name format
- `validate_ollama_url(url)`: Validate Ollama URL (SSRF prevention)
- `is_repo_allowed(repo, allowed_repos)`: Check if repo is in allowlist

**Example:**
```python
from ai_issue_agent.utils.security import SecretRedactor

redactor = SecretRedactor()
safe_text = redactor.redact("My key is sk-abc123")
# Output: "My key is [REDACTED]"
```

### Safe Subprocess Module (`utils/safe_subprocess.py`)

Secure wrapper for GitHub CLI commands.

**Key Classes:**
- `SafeGHCli`: Safe wrapper for `gh` CLI commands
  - `run_command(args, format, timeout)`: Execute a gh CLI command
  - `parse_json_output(output)`: Parse JSON output from gh
  - `check_auth()`: Verify gh authentication status
  - Input validation, never uses `shell=True`

**Error Classes:**
- `GHCliError`, `AuthenticationError`, `RateLimitError`, `NotFoundError`, `PermissionError`, `CommandTimeoutError`

**Example:**
```python
from ai_issue_agent.utils.safe_subprocess import SafeGHCli

gh = SafeGHCli()
result = await gh.run_command(
    ["issue", "create", "--repo", "owner/repo", "--title", "Bug report", "--body", "Description"],
    format="json"
)
```

### Async Helpers Module (`utils/async_helpers.py`)

Utilities for asynchronous operations.

**Key Features:**
- Retry decorators using tenacity with exponential backoff
- Rate limiting utilities
- Custom exception hierarchy: `AgentError`, `TracebackParseError`, `IssueSearchError`, `IssueCreateError`, `LLMAnalysisError`, `RateLimitError`, `SecurityError`, `TimeoutError`

### Health Module (`utils/health.py`)

Health checking for all dependencies.

**Key Classes:**
- `HealthChecker`: Validates config, GitHub CLI auth, LLM provider, Slack tokens
  - `run_all_checks()`: Execute all health checks concurrently
  - Returns `HealthReport` with per-check results and overall status

**Key Enums/Dataclasses:**
- `HealthStatus`: HEALTHY, DEGRADED, UNHEALTHY
- `CheckResult`: Individual check result
- `HealthReport`: Aggregated health report

### Logging Module (`utils/logging.py`)

Structured logging with secret sanitization.

**Key Functions:**
- `configure_logging(level, format, file_path, file_enabled)`: Set up structured logging

**Key Enums/Dataclasses:**
- `LogFormat`: JSON, CONSOLE
- `LogLevel`: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `FileLogConfig`: File logging configuration

### Metrics Module (`utils/metrics.py`)

Observability metrics collection and export.

**Key Classes:**
- `MetricsRegistry`: Singleton metrics registry
  - `Counter`, `Gauge`, `Histogram` metric types
  - `Timer` context manager for timing operations
  - `get_all_metrics()`: Get all metrics as dict
  - `to_prometheus_format()`: Export in Prometheus format

**Pre-defined Metrics:**
- Messages processed, tracebacks detected, issues created/linked
- LLM call counts and latency, cache hit/miss rates
- Rate limit events, security redaction counts

## Module Structure

```
ai_issue_agent/
├── __main__.py        # CLI entry point
├── core/              # Core processing logic
│   ├── agent.py             # Main orchestrator
│   ├── message_handler.py   # Processing pipeline
│   ├── traceback_parser.py  # Python traceback parsing
│   ├── issue_matcher.py     # Issue search & similarity matching
│   └── code_analyzer.py     # Repository code analysis
├── adapters/          # Platform integrations
│   ├── chat/
│   │   └── slack.py         # Slack via slack-bolt
│   ├── vcs/
│   │   └── github.py        # GitHub via gh CLI
│   └── llm/
│       └── anthropic.py     # Anthropic Claude
├── interfaces/        # Abstract protocols
│   ├── chat.py              # ChatProvider protocol
│   ├── vcs.py               # VCSProvider protocol
│   └── llm.py               # LLMProvider protocol
├── models/            # Data models
│   ├── traceback.py         # StackFrame, ParsedTraceback
│   ├── issue.py             # Issue, IssueCreate, IssueMatch
│   ├── message.py           # ChatMessage, ChatReply
│   └── analysis.py          # ErrorAnalysis, SuggestedFix, CodeContext
├── config/            # Configuration
│   ├── schema.py            # Pydantic configuration models
│   └── loader.py            # YAML + env var loading
└── utils/             # Utilities
    ├── security.py          # SecretRedactor, input validation
    ├── safe_subprocess.py   # SafeGHCli wrapper
    ├── async_helpers.py     # Retry, rate limiting, exceptions
    ├── health.py            # Health checks
    ├── logging.py           # Structured logging
    └── metrics.py           # Observability metrics
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

### Issue Models

```python
@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str
    url: str
    state: IssueState
    labels: tuple[str, ...]
    created_at: str
    updated_at: str
    author: str

@dataclass(frozen=True)
class IssueCreate:
    title: str
    body: str
    labels: tuple[str, ...] = ()
    assignees: tuple[str, ...] = ()

@dataclass(frozen=True)
class IssueMatch:
    issue: Issue
    confidence: float
    match_reasons: tuple[str, ...]
```

### Analysis Models

```python
@dataclass(frozen=True)
class CodeContext:
    file_path: str
    start_line: int
    end_line: int
    content: str
    highlight_line: int

@dataclass(frozen=True)
class ErrorAnalysis:
    root_cause: str
    explanation: str
    suggested_fixes: tuple[SuggestedFix, ...]
    related_documentation: tuple[str, ...]
    severity: str
    confidence: float
```

## Full API Documentation

To generate API docs from code:

```bash
# Install with docs dependencies
poetry install --extras docs

# Build and serve documentation
poetry run mkdocs serve

# Build static site
poetry run mkdocs build
```

The API reference will be automatically generated from docstrings using `mkdocstrings[python]`.

## See Also

- [Architecture Documentation](architecture.md) - System design and component interaction
- [Core Components Guide](core-components.md) - Detailed core component documentation
- [Development Setup](setup.md) - Setting up development environment
- [Testing Guide](testing.md) - Writing and running tests
- [Contributing Guide](contributing.md) - Contribution guidelines
