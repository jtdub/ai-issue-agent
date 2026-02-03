# Development Setup

Set up your development environment for AI Issue Agent.

## Prerequisites

- Python 3.11+
- Git
- GitHub CLI (`gh`)
- Code editor (VS Code recommended)

## Clone Repository

```bash
git clone https://github.com/jtdub/ai-issue-agent.git
cd ai-issue-agent
```

## Install Dependencies

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev,docs]"

# Install pre-commit hooks
pre-commit install
```

## Configuration

Copy the example configuration:

```bash
cp config/config.example.yaml config/config.dev.yaml
```

Set up environment variables:

```bash
# Create .env file
cat > .env << 'EOF'
SLACK_BOT_TOKEN=xoxb-your-dev-token
SLACK_APP_TOKEN=xapp-your-dev-token
GITHUB_TOKEN=ghp_your-dev-token
ANTHROPIC_API_KEY=sk-ant-your-dev-key
EOF

# Load environment
source .env
```

## Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/ai_issue_agent --cov-report=html

# Specific test
pytest tests/unit/test_security.py -v

# Watch mode (requires pytest-watch)
ptw
```

## Code Quality

```bash
# Linting
ruff check .

# Formatting
ruff format .

# Type checking
mypy src/

# Security scanning
bandit -r src/

# All checks (runs in pre-commit)
pre-commit run --all-files
```

## Running the Agent

```bash
# Development mode
python -m ai_issue_agent --config config/config.dev.yaml

# With debug logging
python -m ai_issue_agent --config config/config.dev.yaml --log-level DEBUG
```

## IDE Setup

### VS Code

Install recommended extensions:
- Python
- Pylance  
- Ruff
- GitLens

Workspace settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "editor.formatOnSave": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.codeActionsOnSave": {
      "source.fixAll": true,
      "source.organizeImports": true
    }
  }
}
```

## Project Structure

```
ai-issue-agent/
├── src/ai_issue_agent/      # Source code
│   ├── adapters/            # Platform adapters
│   ├── core/                # Core business logic
│   ├── interfaces/          # Abstract interfaces
│   ├── models/              # Data models
│   └── utils/               # Utility functions
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── e2e/                # End-to-end tests
├── docs/                    # Documentation
├── config/                  # Configuration files
└── scripts/                 # Utility scripts
```

## Development Workflow

1. Create feature branch
2. Make changes
3. Run tests and linters
4. Commit with conventional commits
5. Push and create PR
6. Address review feedback
7. Merge when approved

## Debugging

### Using Python Debugger

```python
import pdb; pdb.set_trace()
```

### VS Code Debug Configuration

`.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: AI Issue Agent",
      "type": "python",
      "request": "launch",
      "module": "ai_issue_agent",
      "args": ["--config", "config/config.dev.yaml", "--log-level", "DEBUG"],
      "console": "integratedTerminal",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
      }
    }
  ]
}
```

## Building Documentation

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Serve locally
mkdocs serve

# Build static site
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy
```

## Next Steps

- [Contributing Guidelines](contributing.md)
- [Testing Guide](testing.md)
- [API Reference](api-reference.md)
- [Architecture](architecture.md)
