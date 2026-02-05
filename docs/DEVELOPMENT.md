# Development Guide

This guide covers everything you need to contribute to AI Issue Agent.

## Development Environment Setup

### Prerequisites

- **Python 3.11+** - Required for modern type hints
- **Poetry** - Dependency management
- **Git** - Version control
- **GitHub CLI (`gh`)** - For testing VCS operations
- **VS Code** (recommended) - With Python extension

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/jtdub/ai-issue-agent.git
cd ai-issue-agent

# Install Poetry if needed
curl -sSL https://install.python-poetry.org | python3 -

# Install all dependencies (including dev and docs)
poetry install --with dev,docs

# Activate the virtual environment
poetry shell

# Install pre-commit hooks
pre-commit install
```

### VS Code Setup

Recommended extensions:
- **Python** - Language support
- **Pylance** - Type checking
- **Ruff** - Linting and formatting
- **GitLens** - Git integration

Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.analysis.typeCheckingMode": "strict",
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff"
    },
    "ruff.lint.args": ["--config=pyproject.toml"],
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ]
}
```

### Environment Variables

Create a `.env` file for development:

```bash
# Development tokens (use test workspace)
SLACK_BOT_TOKEN=xoxb-dev-token
SLACK_APP_TOKEN=xapp-dev-token

# Use a test repository
GITHUB_TOKEN=ghp_dev-token

# LLM provider (optional for most development)
ANTHROPIC_API_KEY=sk-ant-dev-key
```

## Running Tests

### Test Suite Overview

```
tests/
├── unit/           # Fast, isolated tests (mocked dependencies)
├── integration/    # Tests with real adapters (mocked external APIs)
├── e2e/            # End-to-end tests (requires credentials)
└── fixtures/       # Test data
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src/ai_issue_agent --cov-report=html
open htmlcov/index.html

# Run specific test file
poetry run pytest tests/unit/test_traceback_parser.py -v

# Run specific test function
poetry run pytest tests/unit/test_traceback_parser.py::test_parse_simple_traceback -v

# Run tests matching a pattern
poetry run pytest -k "traceback" -v

# Run only unit tests
poetry run pytest tests/unit

# Run only fast tests (exclude slow)
poetry run pytest -m "not slow"

# Run with verbose output
poetry run pytest -vvs

# Run in parallel (faster)
poetry run pytest -n auto
```

### Test Markers

```python
import pytest

@pytest.mark.slow
def test_large_repository():
    """This test is slow and can be skipped with -m 'not slow'."""
    pass

@pytest.mark.integration
def test_github_adapter():
    """Requires mocked GitHub API."""
    pass

@pytest.mark.e2e
def test_full_workflow():
    """Requires real credentials."""
    pass
```

### Writing Tests

```python
"""Tests for the traceback parser."""

import pytest
from ai_issue_agent.core.traceback_parser import TracebackParser
from ai_issue_agent.models.traceback import ParsedTraceback


class TestTracebackParser:
    """Test suite for TracebackParser."""

    @pytest.fixture
    def parser(self) -> TracebackParser:
        """Create a parser instance."""
        return TracebackParser()

    def test_parse_simple_traceback(self, parser: TracebackParser) -> None:
        """Test parsing a simple traceback."""
        text = '''
        Traceback (most recent call last):
          File "app.py", line 10, in main
            raise ValueError("test")
        ValueError: test
        '''
        
        result = parser.parse(text)
        
        assert isinstance(result, ParsedTraceback)
        assert result.exception_type == "ValueError"
        assert result.exception_message == "test"
        assert len(result.frames) == 1

    def test_contains_traceback_positive(self, parser: TracebackParser) -> None:
        """Test that contains_traceback returns True for text with traceback."""
        text = "Error:\nTraceback (most recent call last):\n  File..."
        assert parser.contains_traceback(text) is True

    def test_contains_traceback_negative(self, parser: TracebackParser) -> None:
        """Test that contains_traceback returns False for plain text."""
        text = "This is just a normal message"
        assert parser.contains_traceback(text) is False


# Async test example
class TestAsyncComponent:
    """Test async components."""

    @pytest.fixture
    def mock_llm(self, mocker):
        """Create a mock LLM provider."""
        return mocker.Mock()

    @pytest.mark.asyncio
    async def test_async_operation(self, mock_llm) -> None:
        """Test an async method."""
        mock_llm.analyze.return_value = {"result": "test"}
        
        result = await mock_llm.analyze("input")
        
        assert result == {"result": "test"}
```

### Test Fixtures

Fixtures are in `tests/fixtures/`:

```
fixtures/
├── tracebacks/           # Sample Python tracebacks
│   ├── simple.txt
│   ├── nested.txt
│   └── multiline_msg.txt
├── issues/               # Sample GitHub issues
│   └── sample_issues.json
└── security/             # Security test data
    ├── malicious_inputs.txt
    └── secrets.txt
```

Load fixtures in tests:

```python
from pathlib import Path

@pytest.fixture
def simple_traceback() -> str:
    """Load the simple traceback fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures/tracebacks/simple.txt"
    return fixture_path.read_text()
```

## Code Style and Linting

### Ruff (Linting and Formatting)

```bash
# Check for linting issues
poetry run ruff check .

# Fix auto-fixable issues
poetry run ruff check --fix .

# Format code
poetry run ruff format .

# Check formatting without changes
poetry run ruff format --check .
```

### Type Checking (mypy)

```bash
# Run type checking
poetry run mypy src/ai_issue_agent

# With verbose output
poetry run mypy src/ai_issue_agent --verbose
```

Configuration in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
```

### Pre-commit Hooks

Pre-commit runs automatically on `git commit`:

```bash
# Run manually on all files
poetry run pre-commit run --all-files

# Update hooks
poetry run pre-commit autoupdate
```

Configuration in `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-PyYAML
          - types-cachetools
```

## Architecture Overview

### Project Structure

```
src/ai_issue_agent/
├── __init__.py          # Package entry
├── __main__.py          # CLI entry point
├── _version.py          # Version string
│
├── config/              # Configuration
│   ├── schema.py        # Pydantic models
│   └── loader.py        # YAML loading
│
├── interfaces/          # Protocol definitions
│   ├── chat.py          # ChatProvider protocol
│   ├── vcs.py           # VCSProvider protocol
│   └── llm.py           # LLMProvider protocol
│
├── adapters/            # Concrete implementations
│   ├── chat/
│   │   └── slack.py     # Slack adapter
│   ├── vcs/
│   │   └── github.py    # GitHub adapter
│   └── llm/
│       ├── anthropic.py # Anthropic adapter
│       ├── openai.py    # OpenAI adapter
│       └── ollama.py    # Ollama adapter
│
├── core/                # Business logic
│   ├── agent.py         # Main orchestrator
│   ├── traceback_parser.py
│   ├── issue_matcher.py
│   ├── code_analyzer.py
│   └── message_handler.py
│
├── models/              # Data models
│   ├── traceback.py     # ParsedTraceback, StackFrame
│   ├── issue.py         # Issue, IssueCreate
│   ├── message.py       # ChatMessage, ChatReply
│   └── analysis.py      # ErrorAnalysis
│
└── utils/               # Utilities
    ├── security.py      # SecretRedactor
    ├── safe_subprocess.py  # SafeGHCli
    ├── async_helpers.py    # Retry, rate limiting
    ├── logging.py       # Structured logging
    ├── health.py        # Health checks
    └── metrics.py       # Metrics collection
```

### Key Design Patterns

#### Protocol-Based Interfaces

All external integrations use Python protocols:

```python
from typing import Protocol, AsyncIterator

class ChatProvider(Protocol):
    """Interface for chat platform integrations."""
    
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def listen(self) -> AsyncIterator[ChatMessage]: ...
    async def send_reply(self, message: ChatReply) -> None: ...
    async def add_reaction(self, channel: str, message_id: str, emoji: str) -> None: ...
```

#### Dependency Injection

Components receive their dependencies through constructor injection:

```python
class MessageHandler:
    def __init__(
        self,
        chat: ChatProvider,
        vcs: VCSProvider,
        llm: LLMProvider,
        parser: TracebackParser,
        matcher: IssueMatcher,
        analyzer: CodeAnalyzer,
        config: AgentConfig,
    ) -> None:
        self._chat = chat
        self._vcs = vcs
        # ...
```

#### Async-First Design

All I/O operations are async:

```python
async def process_message(self, message: ChatMessage) -> ProcessingResult:
    """Process a message asynchronously."""
    async with self._semaphore:
        result = await self._handler.handle(message)
        return result
```

## Adding New Adapters

### Chat Adapter

Create `src/ai_issue_agent/adapters/chat/discord.py`:

```python
"""Discord chat adapter."""

from typing import AsyncIterator
import discord

from ai_issue_agent.interfaces.chat import ChatProvider
from ai_issue_agent.models.message import ChatMessage, ChatReply


class DiscordAdapter(ChatProvider):
    """Discord implementation of ChatProvider."""

    def __init__(self, token: str, guild_id: str) -> None:
        """Initialize Discord adapter."""
        self._token = token
        self._guild_id = guild_id
        self._client: discord.Client | None = None

    async def connect(self) -> None:
        """Connect to Discord."""
        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        await self._client.start(self._token)

    async def disconnect(self) -> None:
        """Disconnect from Discord."""
        if self._client:
            await self._client.close()

    async def listen(self) -> AsyncIterator[ChatMessage]:
        """Listen for messages."""
        # Implementation...
        pass

    async def send_reply(self, reply: ChatReply) -> None:
        """Send a reply."""
        # Implementation...
        pass

    async def add_reaction(self, channel: str, message_id: str, emoji: str) -> None:
        """Add a reaction."""
        # Implementation...
        pass
```

### VCS Adapter

Create `src/ai_issue_agent/adapters/vcs/gitlab.py`:

```python
"""GitLab VCS adapter."""

from ai_issue_agent.interfaces.vcs import VCSProvider
from ai_issue_agent.models.issue import Issue, IssueCreate, IssueSearchResult


class GitLabAdapter(VCSProvider):
    """GitLab implementation of VCSProvider."""

    def __init__(self, token: str, base_url: str = "https://gitlab.com") -> None:
        """Initialize GitLab adapter."""
        self._token = token
        self._base_url = base_url

    async def search_issues(
        self,
        repo: str,
        query: str,
        include_closed: bool = True,
    ) -> IssueSearchResult:
        """Search issues in GitLab."""
        # Implementation...
        pass

    async def create_issue(self, repo: str, issue: IssueCreate) -> Issue:
        """Create a new issue."""
        # Implementation...
        pass

    async def get_issue(self, repo: str, issue_number: int) -> Issue | None:
        """Get an existing issue."""
        # Implementation...
        pass
```

### Register Adapter

Update `src/ai_issue_agent/core/agent.py`:

```python
async def _create_chat_adapter(config: AgentConfig) -> ChatProvider:
    """Create a chat adapter based on configuration."""
    provider = config.chat.provider

    if provider == "slack":
        # Existing Slack adapter
        pass
    elif provider == "discord":
        from ai_issue_agent.adapters.chat.discord import DiscordAdapter
        return DiscordAdapter(
            token=config.chat.discord.token,
            guild_id=config.chat.discord.guild_id,
        )
    else:
        raise ValueError(f"Unsupported chat provider: {provider}")
```

## Pull Request Guidelines

### Before Submitting

1. **Run all checks**:
   ```bash
   poetry run pytest
   poetry run mypy src/ai_issue_agent
   poetry run ruff check .
   poetry run ruff format --check .
   ```

2. **Update documentation** if needed

3. **Add tests** for new functionality

4. **Update CHANGELOG.md** with your changes

### PR Checklist

- [ ] Tests pass (`poetry run pytest`)
- [ ] Type checking passes (`poetry run mypy src/ai_issue_agent`)
- [ ] Linting passes (`poetry run ruff check .`)
- [ ] Code is formatted (`poetry run ruff format .`)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Commit messages follow conventional commits

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

Examples:
```
feat(parser): add support for chained exceptions

fix(slack): handle rate limits correctly

docs(readme): update installation instructions

test(security): add tests for secret redaction
```

## Documentation

### Building Docs

```bash
# Install docs dependencies
poetry install --with docs

# Serve locally
poetry run mkdocs serve
# Open http://127.0.0.1:8000

# Build static site
poetry run mkdocs build
```

### Docstring Format

Use Google-style docstrings:

```python
def process_traceback(
    self,
    text: str,
    include_locals: bool = False,
) -> ParsedTraceback:
    """Parse a Python traceback from text.

    This method extracts structured information from a Python traceback
    including exception type, message, and stack frames.

    Args:
        text: Raw text that may contain a traceback.
        include_locals: If True, attempt to extract local variables
            from the traceback (if available).

    Returns:
        A ParsedTraceback object containing the structured traceback
        information.

    Raises:
        ParseError: If the traceback cannot be parsed.
        ValueError: If text is empty.

    Example:
        >>> parser = TracebackParser()
        >>> result = parser.process_traceback("Traceback (most recent call last):...")
        >>> print(result.exception_type)
        'ValueError'
    """
```

## Debugging

### Debug Logging

```bash
# Enable debug logging
ai-issue-agent --debug

# Or set in config
logging:
  level: DEBUG
```

### Interactive Debugging

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use IPython
import IPython; IPython.embed()
```

### VS Code Debugging

Create `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug Agent",
            "type": "python",
            "request": "launch",
            "module": "ai_issue_agent",
            "args": ["--config", "config/config.yaml", "--debug"],
            "cwd": "${workspaceFolder}",
            "env": {
                "SLACK_BOT_TOKEN": "xoxb-...",
                "SLACK_APP_TOKEN": "xapp-..."
            }
        },
        {
            "name": "Debug Tests",
            "type": "python",
            "request": "launch",
            "module": "pytest",
            "args": ["-v", "-s", "${file}"],
            "cwd": "${workspaceFolder}"
        }
    ]
}
```

## Release Process

1. Update version in `src/ai_issue_agent/_version.py`
2. Update CHANGELOG.md
3. Create PR and merge to main
4. Tag release: `git tag -a v0.x.0 -m "Release v0.x.0"`
5. Push tag: `git push origin v0.x.0`
6. GitHub Actions will publish to PyPI
