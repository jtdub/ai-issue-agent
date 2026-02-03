# AI Issue Agent

Welcome to the AI Issue Agent documentation! This system automatically monitors chat platforms for Python tracebacks and triages them as GitHub issues using AI-powered analysis.

## Overview

AI Issue Agent is an automation system that:

- **Monitors** chat platforms (Slack, Discord, MS Teams) for error messages
- **Parses** Python tracebacks from chat messages
- **Searches** for existing related GitHub issues
- **Analyzes** errors using LLM providers (OpenAI, Anthropic, Ollama)
- **Creates** detailed GitHub issues with context and suggested fixes

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AI Issue Agent                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │  Chat Adapters  │    │   VCS Adapters  │    │  LLM Adapters   │          │
│  │  (Abstract)     │    │   (Abstract)    │    │  (Abstract)     │          │
│  ├─────────────────┤    ├─────────────────┤    ├─────────────────┤          │
│  │ • Slack         │    │ • GitHub        │    │ • OpenAI        │          │
│  │ • Discord*      │    │ • GitLab*       │    │ • Anthropic     │          │
│  │ • MS Teams*     │    │ • Bitbucket*    │    │ • Ollama/Llama  │          │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘          │
│           │                      │                      │                   │
│           └──────────────────────┼──────────────────────┘                   │
│                                  │                                          │
│                    ┌─────────────▼─────────────┐                            │
│                    │      Core Engine          │                            │
│                    │  ┌─────────────────────┐  │                            │
│                    │  │ Message Processor   │  │                            │
│                    │  │ Traceback Parser    │  │                            │
│                    │  │ Issue Matcher       │  │                            │
│                    │  │ Code Analyzer       │  │                            │
│                    │  │ Issue Creator       │  │                            │
│                    │  └─────────────────────┘  │                            │
│                    └───────────────────────────┘                            │
│                                                                             │
│  * = Future implementation                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Features

### 🤖 AI-Powered Analysis
Leverages large language models to understand error context, suggest fixes, and create comprehensive issue descriptions.

### 🔒 Security-First Design
- Automatic secret redaction before sending data to external services
- Input validation to prevent injection attacks
- SSRF protection for local LLM endpoints
- Fail-closed error handling

### 🔌 Extensible Architecture
Abstract interfaces for chat platforms, version control systems, and LLM providers make it easy to add new integrations.

### ⚡ Async & Scalable
Built on asyncio with rate limiting, retry logic, and efficient resource management.

## Quick Start

=== "pip"
    ```bash
    pip install ai-issue-agent
    ```

=== "pipx"
    ```bash
    pipx install ai-issue-agent
    ```

=== "From source"
    ```bash
    git clone https://github.com/jtdub/ai-issue-agent.git
    cd ai-issue-agent
    pip install -e .
    ```

Configure your environment:

```bash
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."
export GITHUB_TOKEN="ghp_..."
export OPENAI_API_KEY="sk-..."
```

Run the agent:

```bash
ai-issue-agent --config config.yaml
```

## Documentation Sections

### [User Guide](user-guide/getting-started.md)
Learn how to install, configure, and use AI Issue Agent in your workflow.

### [Administrator Guide](admin-guide/overview.md)
Deploy, monitor, and maintain AI Issue Agent in production environments.

### [Developer Guide](developer-guide/architecture.md)
Understand the architecture, contribute code, and extend functionality.

### [Reference](reference/security.md)
Detailed security documentation, implementation plans, and API reference.

## Support

- **Issues**: [GitHub Issues](https://github.com/jtdub/ai-issue-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/jtdub/ai-issue-agent/discussions)
- **Security**: See [Security Policy](reference/security.md)

## License

MIT License - see [LICENSE](https://github.com/jtdub/ai-issue-agent/blob/main/LICENSE) for details.
