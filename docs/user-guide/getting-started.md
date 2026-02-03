# Getting Started

Welcome to AI Issue Agent! This guide will help you get up and running in minutes.

## What is AI Issue Agent?

AI Issue Agent is an automation tool that monitors your team's chat conversations for Python error tracebacks and automatically creates detailed GitHub issues with AI-powered analysis and suggested fixes.

## How It Works

1. **Monitor**: The agent listens to configured Slack channels for messages
2. **Detect**: When a Python traceback is detected in a message, processing begins
3. **Parse**: The traceback is parsed to extract file paths, line numbers, and error details
4. **Search**: GitHub is searched for similar existing issues to avoid duplicates
5. **Analyze**: An LLM analyzes the error, reviews relevant code, and suggests fixes
6. **Create**: A detailed GitHub issue is created with all context and suggestions
7. **Notify**: The original poster is notified with a link to the new issue

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** installed
- **A Slack workspace** with admin access to create bot applications
- **A GitHub account** with permissions to create issues in your repository
- **An API key** for OpenAI, Anthropic, or access to a local Ollama instance

## System Requirements

- **OS**: Linux, macOS, or Windows (WSL recommended)
- **Memory**: 512MB minimum, 1GB recommended
- **Disk**: 100MB for installation + space for repository clones
- **Network**: Stable internet connection for API calls

## Next Steps

Follow these guides in order:

1. [Installation](installation.md) - Install AI Issue Agent
2. [Configuration](configuration.md) - Set up your configuration file
3. [Usage](usage.md) - Start using the agent
4. [Troubleshooting](troubleshooting.md) - Solve common issues

## Quick Example

Here's a preview of what happens when an error is posted to Slack:

**User posts in #errors:**
```
Help! Getting this error in production:

Traceback (most recent call last):
  File "/app/api/handler.py", line 42, in process_request
    result = db.query(user_id)
  File "/app/database/client.py", line 156, in query
    return self.connection.execute(sql)
psycopg2.OperationalError: connection already closed
```

**AI Issue Agent responds:**
- ✅ Adds an "eyes" reaction to show it's processing
- ✅ Searches for similar existing issues (finds none)
- ✅ Clones your repository and analyzes the relevant code
- ✅ Creates a detailed GitHub issue with:
    - Full error details and context
    - Code snippets from the affected files
    - Suggested fixes from AI analysis
    - Link to the original Slack conversation
- ✅ Replies in the thread with the issue link
- ✅ Adds a "white_check_mark" reaction when complete

**Result:**  
[GitHub Issue #123: Database connection already closed in production](https://github.com/yourorg/yourrepo/issues/123)

The issue includes AI-suggested fixes like implementing connection pooling, adding retry logic, and proper connection lifecycle management.

## Support

Need help? Check out:

- [Troubleshooting Guide](troubleshooting.md)
- [Configuration Reference](configuration.md)
- [GitHub Issues](https://github.com/jtdub/ai-issue-agent/issues)
- [Security Guidelines](../reference/security.md)
