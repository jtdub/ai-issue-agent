# Contributing

Thank you for your interest in contributing to AI Issue Agent!

## Code of Conduct

Be respectful, inclusive, and professional in all interactions.

## Getting Started

1. Fork the repository
2. Clone your fork
3. Set up development environment (see [Development Setup](setup.md))
4. Create a feature branch
5. Make your changes
6. Submit a pull request

## Development Process

### 1. Pick an Issue

Browse [open issues](https://github.com/jtdub/ai-issue-agent/issues) or create a new one for discussion.

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 3. Make Changes

- Write clean, documented code
- Follow existing code style
- Add tests for new functionality
- Update documentation as needed

### 4. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/ai_issue_agent --cov-report=term-missing

# Ensure > 90% coverage
```

### 5. Run Linters

```bash
# Format code
ruff format .

# Check for issues
ruff check .

# Type checking
mypy src/

# Pre-commit hooks run all checks
pre-commit run --all-files
```

### 6. Commit Changes

Use [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git commit -m "feat: add support for Discord platform"
git commit -m "fix: resolve secret redaction edge case"
git commit -m "docs: update configuration guide"
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `chore`: Maintenance

### 7. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear description of changes
- Link to related issue
- Screenshots (if UI changes)
- Test results

## Code Style

### Python Style

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use docstrings (Google style)

Example:

```python
def process_message(message: str, config: Config) -> ProcessingResult:
    """Process a chat message for error detection.
    
    Args:
        message: The chat message content.
        config: Configuration settings.
        
    Returns:
        ProcessingResult with detected errors and created issues.
        
    Raises:
        ProcessingError: If message processing fails.
    """
    # Implementation
```

### Testing

- Write unit tests for all new code
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)
- Mock external dependencies

Example:

```python
def test_secret_redactor_redacts_api_keys():
    """Test that API keys are properly redacted."""
    # Arrange
    redactor = SecretRedactor()
    text = "API key: sk-abc123"
    
    # Act
    result = redactor.redact(text)
    
    # Assert
    assert "sk-abc123" not in result
    assert "[REDACTED]" in result
```

## Documentation

- Update docstrings for code changes
- Update MkDocs pages for feature changes
- Add examples for new features
- Keep README.md up to date

## Pull Request Process

1. **CI must pass**: All tests and linters must pass
2. **Review required**: At least one maintainer approval
3. **Up to date**: Rebase on main if needed
4. **Squash commits**: PRs are squashed when merged

## Adding New Features

### New Chat Platform

1. Create adapter in `src/ai_issue_agent/adapters/chat/`
2. Implement `ChatProvider` protocol
3. Add configuration schema
4. Write integration tests
5. Update documentation

### New VCS Provider

1. Create adapter in `src/ai_issue_agent/adapters/vcs/`
2. Implement `VCSProvider` protocol
3. Add CLI wrapper if needed
4. Write integration tests
5. Update documentation

### New LLM Provider

1. Create adapter in `src/ai_issue_agent/adapters/llm/`
2. Implement `LLMProvider` protocol
3. Add rate limiting
4. Write integration tests
5. Update documentation

## Security

- Never commit secrets or tokens
- Review security checklist in SECURITY.md
- Report security issues privately
- Add secret patterns to redactor

## Questions?

- Open a discussion on GitHub
- Join our community chat
- Review existing documentation

Thank you for contributing!
