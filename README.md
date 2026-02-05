# AI Issue Agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

An intelligent automation system that monitors chat platforms (Slack, Discord, Teams) for Python tracebacks and automatically triages them as GitHub issues with LLM-powered analysis.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AI Issue Agent                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │  Chat Adapters  │    │   VCS Adapters  │    │  LLM Adapters   │        │
│  │  (Protocols)    │    │   (Protocols)   │    │  (Protocols)    │        │
│  ├─────────────────┤    ├─────────────────┤    ├─────────────────┤        │
│  │ • Slack         │    │ • GitHub        │    │ • OpenAI        │        │
│  │ • Discord*      │    │ • GitLab*       │    │ • Anthropic     │        │
│  │ • MS Teams*     │    │ • Bitbucket*    │    │ • Ollama/Llama  │        │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘        │
│           │                      │                      │                 │
│           └──────────────────────┼──────────────────────┘                 │
│                                  │                                        │
│                    ┌─────────────▼─────────────┐                          │
│                    │      Core Engine          │                          │
│                    │  ┌─────────────────────┐  │                          │
│                    │  │ Message Processor   │  │                          │
│                    │  │ Traceback Parser    │  │                          │
│                    │  │ Issue Matcher       │  │                          │
│                    │  │ Code Analyzer       │  │                          │
│                    │  │ Issue Creator       │  │                          │
│                    │  └─────────────────────┘  │                          │
│                    └───────────────────────────┘                          │
│                                                                           │
│  * = Future implementation                                                │
└───────────────────────────────────────────────────────────────────────────┘
```

## Features

- **🔍 Automatic Detection**: Monitors chat channels for Python tracebacks
- **🤖 LLM Analysis**: Uses GPT-4, Claude, or local models for error analysis
- **🔗 Smart Matching**: Links to existing issues or creates new ones
- **🔐 Security First**: Built-in secret redaction and input validation
- **🔌 Pluggable Architecture**: Swap chat, VCS, and LLM providers via configuration
- **⚡ Async-First**: All I/O operations use async/await for high performance
- **📊 Type Safe**: Full mypy strict mode compliance
- **🧪 Well Tested**: 80%+ test coverage

## Status

**Current Phase**: Phase 6 - Integration & Polish

✅ **Completed:**
- Phase 1: Project Setup & Core Infrastructure (security utilities, async helpers, CI/CD)
- Phase 2: Data Models & Interfaces (traceback, issue, message, analysis models)
- Phase 3: Traceback Parser (full parser with edge case handling)
- Phase 4: Adapters (Slack, GitHub, Anthropic implementations)
- Phase 5: Core Business Logic (Issue Matcher, Code Analyzer, Message Handler, Agent)

🚧 **In Progress:**
- Phase 6: Integration & Polish (E2E tests, OpenAI/Ollama adapters, documentation)

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the full roadmap.

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [Poetry](https://python-poetry.org/) for dependency management
- GitHub CLI (`gh`) for VCS operations
- Slack workspace with bot permissions (for Slack integration)
- API key for LLM provider (OpenAI, Anthropic, or local Ollama)

### Installation

```bash
# Clone the repository
git clone https://github.com/jtdub/ai-issue-agent.git
cd ai-issue-agent

# Install dependencies with Poetry
poetry install

# Install with development dependencies
poetry install --extras dev

# Install with documentation dependencies
poetry install --extras docs
```

### Configuration

1. Copy the example configuration:
```bash
cp config/config.example.yaml config/config.yaml
```

2. Set required environment variables:
```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_APP_TOKEN="xapp-your-app-token"
export ANTHROPIC_API_KEY="sk-ant-your-api-key"
```

3. Edit `config/config.yaml` to customize settings.

See [docs/user-guide/configuration.md](docs/user-guide/configuration.md) for detailed configuration options.

### Usage

```bash
# Validate configuration
poetry run ai-issue-agent --dry-run

# Run health check
poetry run ai-issue-agent --health-check

# Run the agent
poetry run ai-issue-agent

# Run with debug logging
poetry run ai-issue-agent --debug --format console

# Or activate the virtual environment
poetry shell
ai-issue-agent
```

## Development

### Setup Development Environment

```bash
# Install with all dependencies
poetry install --extras "dev docs"

# Install pre-commit hooks
poetry run pre-commit install

# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=src/ai_issue_agent --cov-report=html

# Type checking
poetry run mypy src/ai_issue_agent

# Linting
poetry run ruff check src tests

# Auto-fix linting issues
poetry run ruff check --fix src tests

# Format code
poetry run ruff format src tests
```

### Project Structure

```
ai-issue-agent/
├── src/
│   └── ai_issue_agent/
│       ├── __init__.py          # Package entry point
│       ├── __main__.py          # CLI entry point
│       ├── _version.py          # Version management
│       ├── adapters/            # Concrete implementations
│       │   ├── chat/            # Slack, Discord, Teams
│       │   ├── llm/             # OpenAI, Anthropic, Ollama
│       │   └── vcs/             # GitHub, GitLab, Bitbucket
│       ├── config/              # Configuration system
│       │   ├── schema.py        # Pydantic models
│       │   └── loader.py        # YAML loading
│       ├── core/                # Business logic
│       │   ├── agent.py         # Main orchestrator
│       │   ├── traceback_parser.py
│       │   ├── issue_matcher.py
│       │   ├── code_analyzer.py
│       │   └── message_handler.py  # Processing pipeline
│       ├── interfaces/          # Protocol definitions
│       │   ├── chat.py          # ChatProvider
│       │   ├── vcs.py           # VCSProvider
│       │   └── llm.py           # LLMProvider
│       ├── models/              # Data models
│       │   ├── traceback.py     # StackFrame, ParsedTraceback
│       │   ├── issue.py         # Issue, IssueCreate
│       │   ├── message.py       # ChatMessage, ChatReply
│       │   └── analysis.py      # ErrorAnalysis, SuggestedFix
│       └── utils/               # Utilities
│           ├── security.py      # SecretRedactor
│           ├── safe_subprocess.py  # SafeGHCli
│           ├── async_helpers.py    # Retry, rate limiting
│           ├── health.py        # Health checks
│           ├── logging.py       # Structured logging
│           └── metrics.py       # Observability metrics
├── tests/
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   ├── e2e/                     # End-to-end tests
│   └── fixtures/                # Test data
├── docs/                        # Documentation
│   ├── ARCHITECTURE.md          # System architecture
│   ├── SECURITY.md              # Security guidelines
│   ├── DEVELOPMENT.md           # Developer guide
│   └── IMPLEMENTATION_PLAN.md   # Roadmap
├── config/                      # Configuration files
│   └── config.example.yaml      # Example config
├── pyproject.toml               # Poetry configuration
└── README.md                    # This file
```

### Running Tests

```bash
# All tests
poetry run pytest

# Unit tests only
poetry run pytest tests/unit

# With coverage report
poetry run pytest --cov=src/ai_issue_agent --cov-report=html
open htmlcov/index.html

# Specific test file
poetry run pytest tests/unit/test_config.py -v

# Run security tests
poetry run pytest tests/unit/test_security.py -v
```

### Documentation

Build and serve documentation locally:

```bash
# Install docs dependencies
poetry install --extras docs

# Serve documentation
poetry run mkdocs serve

# Build documentation
poetry run mkdocs build
```

View at [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Architecture

The project follows a **pluggable adapter pattern** with protocol-based interfaces:

- **ChatProvider**: Abstract interface for chat platforms (Slack, Discord, Teams)
- **VCSProvider**: Abstract interface for version control (GitHub, GitLab, Bitbucket)
- **LLMProvider**: Abstract interface for LLM services (OpenAI, Anthropic, Ollama)

All adapters are swappable via configuration without code changes.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## Security

Security is a top priority. The project implements:

- **Secret Redaction**: 30+ patterns to detect and redact API keys, tokens, passwords
- **Input Validation**: Strict validation of repo names, URLs, and user input
- **SSRF Prevention**: Localhost-only Ollama URLs by default
- **Command Injection Prevention**: Never uses `shell=True`, always validates inputs
- **Fail-Closed**: All security operations fail safely

See [docs/SECURITY.md](docs/SECURITY.md) for comprehensive security documentation.

## Observability

Built-in observability features:

- **Structured Logging**: JSON or console output with secret sanitization
- **Health Checks**: Verify all dependencies are operational
- **Metrics Collection**: Track message processing, issue creation, and errors
- **Context Correlation**: Request IDs and context propagation

```bash
# Run health check
ai-issue-agent --health-check

# Enable JSON logging for log aggregation
ai-issue-agent --format json

# Debug mode for development
ai-issue-agent --debug
```

See [docs/admin-guide/monitoring.md](docs/admin-guide/monitoring.md) for monitoring setup.

## Technology Stack

- **Python**: 3.11+ required for modern type hints
- **Poetry**: Dependency management and packaging
- **Async**: All I/O uses async/await with asyncio
- **Type Checking**: Full strict mypy mode
- **Validation**: Pydantic v2 for data models and configuration
- **Logging**: structlog for structured logging with secret sanitization
- **Testing**: pytest with 80%+ coverage
- **Linting**: ruff for fast linting and formatting
- **Security**: pip-audit for dependency scanning

## Troubleshooting

### Common Issues

**Slack Connection Failed**
```bash
# Verify tokens
echo $SLACK_BOT_TOKEN | head -c 10  # Should show xoxb-
echo $SLACK_APP_TOKEN | head -c 10  # Should show xapp-

# Check Socket Mode is enabled in Slack app settings
```

**GitHub Auth Failed**
```bash
# Re-authenticate
gh auth login

# Verify auth
gh auth status
```

**LLM Errors**
```bash
# Verify API key (Anthropic example)
curl -H "x-api-key: $ANTHROPIC_API_KEY" \
     -H "anthropic-version: 2023-06-01" \
     https://api.anthropic.com/v1/messages \
     -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'
```

**Configuration Errors**
```bash
# Validate configuration
ai-issue-agent --config config/config.yaml --dry-run
```

See [docs/user-guide/troubleshooting.md](docs/user-guide/troubleshooting.md) for more.
Key points:
1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Ensure all tests pass and coverage remains high
5. Run type checking and linting
6. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/jtdub/ai-issue-agent/issues)
- **Documentation**: [docs/](docs/)
- **Security**: See [docs/SECURITY.md](docs/SECURITY.md)

## Acknowledgments

Built with:
- [Poetry](https://python-poetry.org/) for dependency management
- [Pydantic](https://pydantic.dev/) for data validation
- [Ruff](https://github.com/astral-sh/ruff) for linting
- [mypy](http://mypy-lang.org/) for type checking
- [pytest](https://pytest.org/) for testing
- [structlog](https://www.structlog.org/) for logging
- [Anthropic Claude](https://www.anthropic.com/), [OpenAI](https://openai.com/), and [Ollama](https://ollama.ai/) for LLM capabilities
