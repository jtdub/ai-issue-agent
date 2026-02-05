# Deployment Guide

This guide covers everything you need to deploy AI Issue Agent in production.

## Prerequisites

Before deploying, ensure you have:

- **Python 3.11+** - Required for modern type hints and async features
- **GitHub CLI (`gh`)** - For VCS operations
- **Slack Workspace** - With admin access to create apps
- **LLM API Key** - From OpenAI, Anthropic, or local Ollama setup

## Quick Start

```bash
# Install the package
pip install ai-issue-agent

# Or with Poetry
poetry add ai-issue-agent

# Copy example config
cp config/config.example.yaml config/config.yaml

# Set required environment variables
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_APP_TOKEN="xapp-your-app-token"
export ANTHROPIC_API_KEY="sk-ant-your-api-key"

# Authenticate GitHub CLI
gh auth login

# Validate configuration
ai-issue-agent --config config/config.yaml --dry-run

# Run the agent
ai-issue-agent --config config/config.yaml
```

## Slack App Setup

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Enter app name: "AI Issue Agent"
4. Select your workspace

### 2. Configure Socket Mode

Socket Mode allows the app to receive events without exposing a public endpoint.

1. Go to **Socket Mode** in the sidebar
2. Enable Socket Mode
3. Create an **App-Level Token** with `connections:write` scope
4. Save the token (starts with `xapp-`)

### 3. Configure OAuth & Permissions

Go to **OAuth & Permissions** and add these Bot Token Scopes:

| Scope | Purpose |
|-------|---------|
| `chat:write` | Post messages and replies |
| `reactions:write` | Add status reactions |
| `reactions:read` | Read existing reactions |
| `channels:history` | Read messages in channels |
| `channels:read` | List channels |
| `files:read` | Read uploaded files with tracebacks |
| `users:read` | Get user information |

### 4. Subscribe to Events

Go to **Event Subscriptions**:

1. Enable Events
2. Subscribe to Bot Events:
   - `message.channels` - Monitor channel messages
   - `app_mention` - Handle @mentions

### 5. Install to Workspace

1. Go to **Install App**
2. Click **Install to Workspace**
3. Authorize the requested permissions
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 6. Invite Bot to Channels

```
/invite @AI Issue Agent
```

Invite the bot to channels you want it to monitor.

## GitHub Authentication

The agent uses GitHub CLI (`gh`) for all VCS operations.

### Install GitHub CLI

=== "macOS"
    ```bash
    brew install gh
    ```

=== "Ubuntu/Debian"
    ```bash
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
        sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | \
        sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    sudo apt update && sudo apt install gh
    ```

### Authenticate

```bash
# Interactive authentication
gh auth login

# Or use a token
export GITHUB_TOKEN="ghp_your-token"
gh auth login --with-token <<< "$GITHUB_TOKEN"
```

### Required Token Scopes

When creating a Personal Access Token (PAT), include:

- `repo` - Full repository access (for private repos)
- `read:org` - Read organization data
- `workflow` - Update GitHub Actions workflows (if needed)

For **Fine-Grained PATs**, grant access to specific repositories with:
- Read access to code and metadata
- Read and write access to issues

## LLM Provider Setup

### Anthropic (Recommended)

1. Get API key from [console.anthropic.com](https://console.anthropic.com)
2. Set environment variable:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```
3. Configure in `config.yaml`:
   ```yaml
   llm:
     provider: anthropic
     anthropic:
       api_key: ${ANTHROPIC_API_KEY}
       model: "claude-3-5-sonnet-20241022"
       max_tokens: 4096
       temperature: 0.3
   ```

### OpenAI

1. Get API key from [platform.openai.com](https://platform.openai.com)
2. Set environment variable:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```
3. Configure in `config.yaml`:
   ```yaml
   llm:
     provider: openai
     openai:
       api_key: ${OPENAI_API_KEY}
       model: "gpt-4-turbo-preview"
       max_tokens: 4096
       temperature: 0.3
   ```

### Ollama (Local)

For local LLM deployment:

1. Install Ollama: [ollama.ai](https://ollama.ai)
2. Pull a model:
   ```bash
   ollama pull llama2:70b
   ```
3. Configure in `config.yaml`:
   ```yaml
   llm:
     provider: ollama
     ollama:
       base_url: "http://localhost:11434"
       model: "llama2:70b"
       timeout: 120
       allow_remote_host: false  # Security: only localhost allowed
   ```

## Configuration File

Create `config/config.yaml`:

```yaml
# Chat Platform
chat:
  provider: slack
  slack:
    bot_token: ${SLACK_BOT_TOKEN}
    app_token: ${SLACK_APP_TOKEN}
    channels:
      - "#errors"
      - "#production-alerts"
    processing_reaction: "eyes"
    complete_reaction: "white_check_mark"
    error_reaction: "x"

# Version Control
vcs:
  provider: github
  github:
    default_repo: "myorg/myproject"
    clone_dir: "/tmp/ai-issue-agent/repos"
    clone_cache_ttl: 3600
    default_labels:
      - "auto-triaged"
      - "needs-review"
  channel_repos:
    "#frontend-errors": "myorg/frontend"
    "#backend-errors": "myorg/backend"

# LLM Provider
llm:
  provider: anthropic
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    model: "claude-3-5-sonnet-20241022"

# Issue Matching
matching:
  confidence_threshold: 0.85
  max_search_results: 20
  include_closed: true

# Logging
logging:
  level: INFO
  format: json
  file:
    enabled: true
    path: "/var/log/ai-issue-agent/agent.log"
    rotation: "10 MB"
    retention: 7

# Runtime
runtime:
  max_concurrent: 5
  processing_timeout: 300
```

## Running the Agent

### Direct Execution

```bash
# Validate configuration first
ai-issue-agent --config config/config.yaml --dry-run

# Run health check
ai-issue-agent --config config/config.yaml --health-check

# Start the agent
ai-issue-agent --config config/config.yaml

# With debug logging
ai-issue-agent --config config/config.yaml --debug

# With JSON log output (for log aggregation)
ai-issue-agent --config config/config.yaml --format json
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `--config`, `-c` | Path to configuration file |
| `--debug`, `-d` | Enable debug logging |
| `--dry-run` | Validate config without starting |
| `--health-check` | Run health checks and exit |
| `--format` | Log format: `json` or `console` |
| `--version` | Show version |

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
    dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | \
    tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
    apt-get update && \
    apt-get install -y gh && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 agent

# Set up application
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction

COPY src/ ./src/
COPY config/ ./config/

# Switch to non-root user
USER agent

# Create directories
RUN mkdir -p /tmp/ai-issue-agent/repos

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ai-issue-agent --config /app/config/config.yaml --health-check

# Run agent
ENTRYPOINT ["ai-issue-agent"]
CMD ["--config", "/app/config/config.yaml"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  ai-issue-agent:
    build: .
    container_name: ai-issue-agent
    restart: unless-stopped
    
    volumes:
      - ./config.yaml:/app/config/config.yaml:ro
      - ./repos:/tmp/ai-issue-agent/repos
      - ./logs:/var/log/ai-issue-agent
      - gh-auth:/home/agent/.config/gh  # Persist gh auth
    
    environment:
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
      - SLACK_APP_TOKEN=${SLACK_APP_TOKEN}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
    
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  gh-auth:
```

### Running with Docker

```bash
# Build image
docker build -t ai-issue-agent .

# Create .env file
cat > .env << EOF
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
GITHUB_TOKEN=ghp_your-token
ANTHROPIC_API_KEY=sk-ant-your-key
EOF

# Start with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f

# Check health
docker-compose exec ai-issue-agent ai-issue-agent --health-check

# Stop
docker-compose down
```

## Systemd Service

For non-containerized Linux deployments:

### Create Service File

```ini
# /etc/systemd/system/ai-issue-agent.service
[Unit]
Description=AI Issue Agent
After=network.target

[Service]
Type=simple
User=ai-issue-agent
Group=ai-issue-agent
WorkingDirectory=/opt/ai-issue-agent

# Environment
Environment="PATH=/opt/ai-issue-agent/venv/bin:/usr/bin"
EnvironmentFile=/opt/ai-issue-agent/.env

# Execution
ExecStart=/opt/ai-issue-agent/venv/bin/ai-issue-agent --config /opt/ai-issue-agent/config.yaml
ExecReload=/bin/kill -HUP $MAINPID

# Restart policy
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/ai-issue-agent /tmp/ai-issue-agent /var/log/ai-issue-agent
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

### Setup Commands

```bash
# Create user
sudo useradd -r -s /bin/false ai-issue-agent

# Create directories
sudo mkdir -p /opt/ai-issue-agent /var/log/ai-issue-agent
sudo chown -R ai-issue-agent:ai-issue-agent /opt/ai-issue-agent /var/log/ai-issue-agent

# Install application
cd /opt/ai-issue-agent
python3.11 -m venv venv
source venv/bin/activate
pip install ai-issue-agent

# Copy configuration
cp config.yaml /opt/ai-issue-agent/
cp .env /opt/ai-issue-agent/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable ai-issue-agent
sudo systemctl start ai-issue-agent

# Check status
sudo systemctl status ai-issue-agent
sudo journalctl -u ai-issue-agent -f
```

## Monitoring

### Health Checks

```bash
# CLI health check
ai-issue-agent --health-check

# Returns exit code 0 if healthy, 1 if unhealthy
```

### Log Monitoring

Logs are structured JSON for easy parsing:

```bash
# Tail logs
tail -f /var/log/ai-issue-agent/agent.log | jq .

# Filter by level
tail -f /var/log/ai-issue-agent/agent.log | jq 'select(.level == "error")'

# Watch for issue creation
tail -f /var/log/ai-issue-agent/agent.log | jq 'select(.event == "issue_created")'
```

### Metrics

The agent exposes internal metrics:

```python
from ai_issue_agent.utils.metrics import get_metrics

metrics = get_metrics()
print(metrics.get_all_metrics())
```

Key metrics:
- `messages_processed` - Total messages processed
- `issues_created` - New issues created
- `issues_linked` - Linked to existing issues
- `processing_duration` - Processing time histogram
- `llm_requests` - LLM API calls
- `cache_hits` / `cache_misses` - Cache efficiency

### Alerting

Set up alerts for:

1. **Error rate spike** - Too many `message_error` events
2. **Health check failures** - Service unhealthy
3. **Rate limits** - Hitting API rate limits
4. **Long processing time** - Timeouts

Example Prometheus alert:

```yaml
groups:
  - name: ai-issue-agent
    rules:
      - alert: HighErrorRate
        expr: rate(ai_issue_agent_messages_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in AI Issue Agent"
```

## Troubleshooting

### Common Issues

#### Slack Connection Failed

```
Error: Failed to connect to Slack
```

**Solutions:**
1. Verify `SLACK_BOT_TOKEN` starts with `xoxb-`
2. Verify `SLACK_APP_TOKEN` starts with `xapp-`
3. Check Socket Mode is enabled
4. Verify app is installed to workspace

#### GitHub Auth Failed

```
Error: GitHub CLI not authenticated
```

**Solutions:**
1. Run `gh auth login`
2. Verify token has required scopes
3. Check `gh auth status`

#### LLM API Errors

```
Error: LLM request failed
```

**Solutions:**
1. Verify API key is valid
2. Check rate limits
3. Try a different model
4. For Ollama, ensure model is pulled

#### Memory Issues

```
Error: Out of memory
```

**Solutions:**
1. Reduce `max_concurrent` in config
2. Increase container memory limit
3. Check for memory leaks in long-running processes

### Debug Mode

Enable verbose logging:

```bash
ai-issue-agent --config config.yaml --debug
```

### Getting Help

1. Check [GitHub Issues](https://github.com/jtdub/ai-issue-agent/issues)
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) for design details
3. See [SECURITY.md](SECURITY.md) for security configuration
