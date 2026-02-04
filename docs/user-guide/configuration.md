# Configuration

This guide covers all configuration options for AI Issue Agent.

## Configuration File

AI Issue Agent uses YAML for configuration. Create a `config.yaml` file:

```yaml
chat:
  provider: slack
  slack:
    bot_token: ${SLACK_BOT_TOKEN}
    app_token: ${SLACK_APP_TOKEN}
    channels:
      - "#errors"

vcs:
  provider: github
  github:
    default_repo: "myorg/myproject"

llm:
  provider: anthropic
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    model: "claude-3-sonnet-20240229"
```

## Environment Variables

Set required environment variables:

```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_APP_TOKEN="xapp-your-app-token"
export GITHUB_TOKEN="ghp_your-github-token"
export ANTHROPIC_API_KEY="sk-ant-your-api-key"
```

Or use a `.env` file:

```bash
# .env
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
GITHUB_TOKEN=ghp_your-github-token
ANTHROPIC_API_KEY=sk-ant-your-api-key
```

## Integration Setup

### Slack Integration

1. **Create a Slack App** at [api.slack.com/apps](https://api.slack.com/apps)

2. **Configure OAuth Scopes**:
    - `chat:write` - Post messages
    - `reactions:write` - Add reactions
    - `channels:history` - Read messages
    - `channels:read` - List channels
    - `files:read` - Read uploaded files

3. **Enable Socket Mode**:
    - Go to Socket Mode in your app settings
    - Enable Socket Mode
    - Generate an App-Level Token with `connections:write` scope

4. **Subscribe to Events**:
    - `message.channels` - Monitor channel messages
    - `app_mention` - Handle @mentions

5. **Install to Workspace** and copy the Bot Token and App Token

### GitHub Integration

1. **Generate a Personal Access Token**:
    - Go to GitHub Settings → Developer settings → Personal access tokens
    - Create a token with:
        - `repo` - Full repository access
        - `read:org` - Read organization data

2. **Authenticate GitHub CLI**:
    ```bash
    gh auth login
    ```

### LLM Provider Setup

=== "OpenAI"
    1. Get API key from [platform.openai.com](https://platform.openai.com)
    2. Set environment variable:
    ```bash
    export OPENAI_API_KEY="sk-..."
    ```
    3. Configure in config.yaml:
    ```yaml
    llm:
      provider: openai
      openai:
        api_key: ${OPENAI_API_KEY}
        model: "gpt-4-turbo-preview"
    ```

=== "Anthropic"
    1. Get API key from [console.anthropic.com](https://console.anthropic.com)
    2. Set environment variable:
    ```bash
    export ANTHROPIC_API_KEY="sk-ant-..."
    ```
    3. Configure in config.yaml:
    ```yaml
    llm:
      provider: anthropic
      anthropic:
        api_key: ${ANTHROPIC_API_KEY}
        model: "claude-3-5-sonnet-20241022"  # Or claude-3-5-haiku-20241022
    ```

=== "Ollama (Local)"
    1. Install Ollama: [ollama.ai](https://ollama.ai)
    2. Pull a model:
    ```bash
    ollama pull llama2:70b
    ```
    3. Configure in config.yaml:
    ```yaml
    llm:
      provider: ollama
      ollama:
        base_url: "http://localhost:11434"
        model: "llama2:70b"
    ```

## Configuration Options

### Chat Platform Settings

```yaml
chat:
  provider: slack  # or "discord", "teams"
  
  slack:
    bot_token: ${SLACK_BOT_TOKEN}       # Required
    app_token: ${SLACK_APP_TOKEN}       # Required
    
    channels:                            # Channels to monitor
      - "#errors"
      - "#production-alerts"
      - "C1234567890"                    # Can use channel IDs
    
    processing_reaction: "eyes"          # Reaction when processing starts
    complete_reaction: "white_check_mark"  # Reaction when complete
    error_reaction: "x"                  # Reaction on error
```

### Version Control Settings

```yaml
vcs:
  provider: github  # or "gitlab", "bitbucket"
  
  github:
    default_repo: "myorg/myproject"     # Default repository
    clone_dir: "/tmp/ai-issue-agent/repos"  # Clone directory
    clone_cache_ttl: 3600               # Cache TTL in seconds
    
    default_labels:                      # Labels for created issues
      - "auto-triaged"
      - "needs-review"
    
    allowed_repos: []                    # Restrict to specific repos
    
  channel_repos:                         # Map channels to repos
    "#frontend-errors": "myorg/frontend"
    "#backend-errors": "myorg/backend"
  
  allow_public_repos: false             # Require explicit opt-in
```

### LLM Provider Settings

```yaml
llm:
  provider: anthropic  # or "openai", "ollama"
  
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    model: "claude-3-sonnet-20240229"
    max_tokens: 4096
    temperature: 0.3
```

### Issue Matching Settings

```yaml
matching:
  confidence_threshold: 0.85            # Minimum match confidence
  max_search_results: 20                # Max issues to search
  include_closed: true                  # Search closed issues
  search_cache_ttl: 300                 # Cache TTL in seconds
  
  weights:                              # Matching criteria weights
    exception_type: 0.3
    exception_message: 0.4
    stack_frames: 0.2
    semantic_similarity: 0.1
```

### Code Analysis Settings

```yaml
analysis:
  context_lines: 15                     # Lines of context around error
  max_files: 10                         # Max files to analyze
  
  skip_paths:                           # Skip these paths
    - "/usr/lib/python"
    - "site-packages"
  
  include_files:                        # Always include these
    - "README.md"
    - "pyproject.toml"
```

### Logging Settings

```yaml
logging:
  level: INFO                           # DEBUG, INFO, WARNING, ERROR
  format: json                          # json or console
  
  file:
    enabled: false
    path: "/var/log/ai-issue-agent/agent.log"
    rotation: "10 MB"
    retention: 7                        # days
```

### Runtime Settings

```yaml
runtime:
  max_concurrent: 5                     # Concurrent message processing
  processing_timeout: 300               # Timeout in seconds
  
  retry:
    max_attempts: 3
    initial_delay: 1.0
    max_delay: 30.0
    exponential_base: 2.0
```

## Configuration Validation

Validate your configuration:

```bash
ai-issue-agent --config config.yaml --validate
```

## Example Configurations

### Minimal Configuration

```yaml
chat:
  provider: slack
  slack:
    bot_token: ${SLACK_BOT_TOKEN}
    app_token: ${SLACK_APP_TOKEN}

vcs:
  provider: github
  github:
    default_repo: "myorg/myproject"

llm:
  provider: anthropic
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
```

### Production Configuration

```yaml
chat:
  provider: slack
  slack:
    bot_token: ${SLACK_BOT_TOKEN}
    app_token: ${SLACK_APP_TOKEN}
    channels:
      - "#production-errors"
      - "#staging-errors"

vcs:
  provider: github
  github:
    default_repo: "myorg/production-app"
    allowed_repos:
      - "myorg/production-app"
      - "myorg/shared-library"
    default_labels:
      - "auto-triaged"
      - "production"
      - "needs-investigation"

llm:
  provider: anthropic
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    model: "claude-3-sonnet-20240229"
    temperature: 0.1

logging:
  level: INFO
  format: json
  file:
    enabled: true
    path: "/var/log/ai-issue-agent/agent.log"
    rotation: "50 MB"
    retention: 30

runtime:
  max_concurrent: 10
  processing_timeout: 600
```

## Next Steps

- [Usage Guide](usage.md) - Learn how to use the agent
- [Troubleshooting](troubleshooting.md) - Solve common issues
- [Security Best Practices](../reference/security.md)
