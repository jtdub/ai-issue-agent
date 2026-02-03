# Usage

Learn how to use AI Issue Agent in your daily workflow.

## Starting the Agent

Start the agent with your configuration file:

```bash
ai-issue-agent --config config.yaml
```

The agent will:
1. Load and validate configuration
2. Connect to Slack (Socket Mode)
3. Authenticate with GitHub
4. Initialize the LLM provider
5. Start monitoring configured channels

## How It Works

### 1. Message Detection

The agent monitors Slack channels for messages containing Python tracebacks:

```
Traceback (most recent call last):
  File "/app/api/handler.py", line 42, in process_request
    result = db.query(user_id)
ValueError: Invalid user ID format
```

### 2. Processing Workflow

When a traceback is detected:

1. **Acknowledgment** - Adds 👀 reaction to show processing has started
2. **Parsing** - Extracts stack frames, exception type, and message
3. **Searching** - Searches GitHub for similar existing issues
4. **Analysis** - LLM analyzes the error and suggests fixes
5. **Issue Creation** - Creates a GitHub issue with all context
6. **Notification** - Posts issue link in Slack thread
7. **Completion** - Adds ✅ reaction

### 3. GitHub Issue Content

Created issues include:

- **Title**: Concise error summary
- **Description**:
    - Full traceback with syntax highlighting
    - Link to original Slack conversation
    - Environment details (if available)
- **Analysis**:
    - Root cause explanation
    - Code context from affected files
    - Suggested fixes and workarounds
- **Labels**: Auto-assigned labels for triage

## Command-Line Options

```bash
# Basic usage
ai-issue-agent --config config.yaml

# Validate configuration without running
ai-issue-agent --config config.yaml --validate

# Set log level
ai-issue-agent --config config.yaml --log-level DEBUG

# Dry run (don't create issues)
ai-issue-agent --config config.yaml --dry-run

# Process specific message
ai-issue-agent --config config.yaml --process-url https://...slack.com/...
```

## Usage Patterns

### Single Repository

Monitor errors for one project:

```yaml
vcs:
  github:
    default_repo: "myorg/myapp"
chat:
  slack:
    channels:
      - "#errors"
```

### Multiple Repositories

Map channels to different repositories:

```yaml
vcs:
  github:
    default_repo: "myorg/backend"
  channel_repos:
    "#frontend-errors": "myorg/frontend"
    "#backend-errors": "myorg/backend"
    "#mobile-errors": "myorg/mobile-app"
```

### Team-Based Routing

Use channel naming conventions:

```yaml
chat:
  slack:
    channels:
      - "#team-platform-errors"
      - "#team-data-errors"
      - "#team-infra-errors"
```

## Best Practices

### Channel Setup

- **Dedicated error channels**: Create channels specifically for error reporting
- **Clear naming**: Use descriptive names like `#production-errors`
- **Team-specific**: Consider per-team error channels
- **Private vs public**: Use private channels for sensitive errors

### Message Format

Encourage team members to post errors with context:

```
Production issue in user authentication:

Environment: production
Timestamp: 2024-02-03 14:23:45 UTC
User ID: user_123

Traceback (most recent call last):
  File "/app/auth/handler.py", line 67, in validate_token
    user = cache.get(token)
  File "/app/cache/redis.py", line 34, in get
    return self.client.get(key)
redis.exceptions.ConnectionError: Connection refused
```

### Issue Deduplication

The agent automatically searches for similar issues. To improve matching:

- Keep error messages consistent
- Use descriptive variable names in code
- Include stack traces when reporting errors

### Monitoring

Check agent health:

```bash
# View logs
tail -f /var/log/ai-issue-agent/agent.log

# Check process status
ps aux | grep ai-issue-agent

# View created issues
gh issue list --repo myorg/myapp --label auto-triaged
```

## Interactive Commands

Post these in monitored channels:

```
@ai-issue-agent help           # Show help message
@ai-issue-agent status         # Show agent status
@ai-issue-agent reprocess      # Reprocess a message (reply to message)
@ai-issue-agent search <query> # Search for similar issues
```

## Examples

### Example 1: Production Error

**Slack message:**
```
🚨 Production alert - payment processing failing

Traceback (most recent call last):
  File "/app/payments/processor.py", line 145, in process_payment
    response = stripe.charge.create(...)
stripe.error.CardError: Your card was declined
```

**AI Issue Agent creates:**
- GitHub issue: "Payment processing fails with declined cards"
- Includes: Full trace, Stripe API documentation links, retry strategies
- Labels: `auto-triaged`, `payment`, `production`

### Example 2: Database Connection Issue

**Slack message:**
```
Getting intermittent database errors on staging:

Traceback (most recent call last):
  File "/app/db/pool.py", line 89, in get_connection
    conn = self.pool.getconn()
psycopg2.pool.PoolError: connection pool exhausted
```

**AI Issue Agent creates:**
- GitHub issue: "Database connection pool exhaustion on staging"
- Includes: Pool configuration analysis, connection leak detection tips
- Labels: `auto-triaged`, `database`, `staging`
- Finds similar closed issue and references it

## Tips & Tricks

### Ignoring Messages

Add `[no-issue]` to messages you don't want processed:

```
[no-issue] This is a known issue, already tracking in #123

Traceback...
```

### Priority Issues

Add `[urgent]` or `[critical]` for priority labeling:

```
[urgent] Production down!

Traceback...
```

### Custom Labels

Configure custom label patterns:

```yaml
vcs:
  github:
    label_rules:
      - pattern: "\\[urgent\\]"
        labels: ["urgent", "priority:high"]
      - pattern: "production"
        labels: ["production"]
```

## Stopping the Agent

```bash
# Graceful shutdown (SIGTERM)
kill -TERM $(pgrep -f ai-issue-agent)

# Or use Ctrl+C if running in foreground
```

The agent will:
1. Stop accepting new messages
2. Complete processing of current messages
3. Close connections gracefully
4. Exit cleanly

## Next Steps

- [Troubleshooting](troubleshooting.md) - Solve common issues
- [Admin Guide](../admin-guide/overview.md) - Production deployment
- [API Reference](../developer-guide/api-reference.md) - Extend functionality
