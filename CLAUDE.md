# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Issue Agent is an automation system that monitors chat platforms (Slack) for Python tracebacks and automatically triages them as GitHub issues. When a traceback is detected, it parses the error, searches for existing related issues, and either links to an existing issue or creates a new one with LLM-powered analysis.

**Status**: Architecture/blueprint phase - no implementation code yet.

## Technology Stack

- **Python**: >=3.11 required
- **Async**: All I/O uses async/await with asyncio
- **Type checking**: Full strict mypy mode
- **Validation**: Pydantic v2 for data models and configuration
- **Logging**: structlog (not stdlib logging)
- **Retry logic**: tenacity with exponential backoff
- **VCS operations**: Uses `gh` CLI tool (not library APIs)

## Commands

Once implemented, the planned commands are:

```bash
# Run the agent
python -m ai_issue_agent

# Run tests
pytest                          # All tests
pytest tests/unit               # Unit tests only
pytest tests/integration        # Integration tests only
pytest -k "test_name"           # Single test by name

# Type checking
mypy

# Lint and format
ruff check                      # Lint
ruff format                     # Format
ruff check --fix                # Auto-fix lint issues
```

## Architecture

### Design Principles

1. **Pluggable adapters**: Chat, VCS, and LLM providers are swappable via configuration
2. **Async-first**: All I/O operations use async/await
3. **Protocol-based interfaces**: Use `typing.Protocol`, not ABC
4. **CLI-based VCS**: Shell out to `gh` CLI for GitHub operations (simplifies auth)

### Core Components

| Component | Responsibility |
|-----------|---------------|
| `Agent` | Main orchestrator - coordinates adapters, manages message processing |
| `TracebackParser` | Detects and parses Python tracebacks from text |
| `IssueMatcher` | Searches for and ranks existing issues by similarity |
| `CodeAnalyzer` | Clones repos and extracts code context for stack frames |
| `MessageHandler` | Orchestrates the processing pipeline |

### Abstract Interfaces (Protocols)

- `ChatProvider`: connect, disconnect, listen for messages, send replies, manage reactions
- `VCSProvider`: search/create issues, clone repos, get file contents
- `LLMProvider`: analyze errors, generate issue titles/bodies, calculate similarity

### Planned Directory Structure

```
src/ai_issue_agent/
├── config/         # Pydantic config schema and YAML loader
├── interfaces/     # Protocol definitions (chat.py, vcs.py, llm.py)
├── adapters/       # Implementations (slack, github, anthropic/openai/ollama)
├── core/           # Business logic (agent, parser, matcher, analyzer, handler)
├── models/         # Data classes (traceback, issue, message, analysis)
└── utils/          # Async helpers, retry decorators, security utilities
    ├── security.py       # SecretRedactor, input validation
    └── safe_subprocess.py # SafeGHCli wrapper
```

### Workflow

1. Message received -> Add :eyes: reaction
2. Check for traceback -> If none, remove reaction and ignore
3. Parse traceback -> Search existing issues
4. If high-confidence match (>=0.85) -> Reply with link
5. If no match -> Clone repo -> Extract code context -> LLM analysis -> Create issue -> Reply
6. Update reaction to :white_check_mark: (or :x: on error)

## Configuration

YAML config with environment variable substitution (`${VAR_NAME}`). Key sections:
- `chat`: Provider and credentials (Slack tokens, channels)
- `vcs`: Provider and settings (default repo, labels, clone dir)
- `llm`: Provider and API keys (OpenAI/Anthropic/Ollama)
- `matching`: Confidence threshold (0.85 default), search limits
- `analysis`: Context lines, max files to analyze

## Testing

- **pytest-asyncio** for async tests (uses `asyncio_mode = "auto"`)
- Test pyramid: 60% unit, 30% integration, 10% E2E
- Coverage targets: 80% overall, 90%+ for core modules
- Mock external services (Slack, GitHub, LLM APIs) in integration tests

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `slack-bolt` | Slack SDK with async support |
| `pydantic` / `pydantic-settings` | Data validation, config management |
| `openai` / `anthropic` | LLM provider clients |
| `httpx` | Async HTTP for Ollama |
| `structlog` | Structured logging |
| `tenacity` | Retry with backoff |

## Security

See [docs/SECURITY.md](docs/SECURITY.md) for comprehensive security documentation including the canonical list of secret patterns, threat model, and security checklist.

### Critical Security Rules

1. **Fail closed** - All security operations must fail closed. If redaction fails, block the LLM call entirely.

2. **Never send unredacted tracebacks to LLMs** - Tracebacks contain secrets (API keys, passwords, connection strings). Always run through `SecretRedactor` first.

3. **Never use `shell=True`** - All subprocess calls must use list arguments to prevent command injection.

4. **Validate repository names** - Must match `^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$` before any `gh` CLI operation.

5. **Disable git hooks on clone** - Use `-c core.hooksPath=/dev/null` to prevent malicious hook execution.

6. **Redact before creating issues** - Apply the same secret redaction to issue bodies before creating GitHub issues.

7. **Validate Ollama URLs** - Only allow localhost by default to prevent SSRF attacks. Non-localhost requires explicit `allow_remote_host: true`.

8. **Validate LLM output** - All LLM responses must pass Pydantic schema validation before use.

### Required Security Components

- `utils/security.py`: `SecretRedactor` class (see SECURITY.md for canonical pattern list)
- `utils/safe_subprocess.py`: `SafeGHCli` wrapper that validates inputs and uses list-based subprocess calls

### Quick Reference: Key Patterns

See SECURITY.md for the full canonical list. Critical patterns include:
- Slack tokens: `xox[baprs]-`
- GitHub tokens: `ghp_`, `github_pat_`, `gho_`, `ghu_`, `ghs_`
- OpenAI: `sk-` (legacy), `sk-proj-` (project)
- Anthropic: `sk-ant-`
- AWS: `AKIA` (access key), connection strings with credentials
- Private keys: `-----BEGIN.*PRIVATE KEY-----`
- JWT: `eyJ...` (three base64 sections)
