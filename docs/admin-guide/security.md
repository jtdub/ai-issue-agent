# Security

Security best practices and hardening guidelines for AI Issue Agent.

## Overview

AI Issue Agent handles sensitive data from multiple sources:
- Chat messages containing error tracebacks
- Source code from repositories
- API credentials for external services

This guide covers security hardening for production deployments.

## Credential Management

### Never Store Secrets in Code

❌ **Wrong:**
```yaml
slack:
  bot_token: "xoxb-1234567890-1234567890-abc123def456"
```

✅ **Correct:**
```yaml
slack:
  bot_token: ${SLACK_BOT_TOKEN}
```

### Use Secrets Managers

For production deployments, use a secrets manager:

- **AWS Secrets Manager**
- **HashiCorp Vault**
- **Azure Key Vault**
- **GCP Secret Manager**
- **Kubernetes Secrets** (with encryption at rest)

### Environment Variable Security

```bash
# Never export secrets in shell history
read -s SLACK_BOT_TOKEN && export SLACK_BOT_TOKEN

# Use .env file with proper permissions
chmod 600 .env

# In Docker, use secrets
docker secret create slack_token slack_token.txt
```

### Rotate Credentials Regularly

Establish rotation schedules:

| Credential | Rotation Period | Notes |
|------------|-----------------|-------|
| Slack tokens | 90 days | Revoke old tokens in Slack admin |
| GitHub tokens | 90 days | Use fine-grained PATs with expiration |
| LLM API keys | 90 days | Monitor usage for anomalies |

## Required Token Scopes

### Slack Bot Token Scopes (Minimal)

| Scope | Purpose | Required |
|-------|---------|----------|
| `chat:write` | Post messages and replies | ✅ Yes |
| `reactions:write` | Add status reactions | ✅ Yes |
| `reactions:read` | Read existing reactions | ✅ Yes |
| `channels:history` | Read channel messages | ✅ Yes |
| `channels:read` | List channels | ⚠️ Optional |
| `files:read` | Read uploaded files | ⚠️ Optional |
| `users:read` | Get user information | ⚠️ Optional |

**Do NOT grant:** `admin`, `admin.*`, `team:read`, or any scope not listed.

### Slack App Token Scopes

| Scope | Purpose | Required |
|-------|---------|----------|
| `connections:write` | Socket Mode connection | ✅ Yes |

### GitHub Token Scopes

For **Classic Personal Access Tokens**:

| Scope | Purpose | Required |
|-------|---------|----------|
| `repo` | Access private repositories | ✅ For private repos |
| `public_repo` | Access public repositories | ✅ For public repos |
| `read:org` | Read organization data | ⚠️ If using org repos |

**Do NOT grant:** `admin:*`, `delete_repo`, `write:org`

For **Fine-Grained Personal Access Tokens** (recommended):
- Repository access: Select specific repositories only
- Permissions:
  - Contents: Read
  - Issues: Read and write
  - Metadata: Read

## Access Control

### Principle of Least Privilege

Configure minimal repository access:

```yaml
vcs:
  github:
    # Only allow specific repositories
    allowed_repos:
      - "myorg/app1"
      - "myorg/app2"
      - "myorg/*"  # Wildcard for all org repos
    
    # Disable public repo access unless needed
    allow_public_repos: false
```

### Channel-to-Repository Mapping

Restrict which channels can create issues in which repos:

```yaml
vcs:
  channel_repos:
    "#frontend-errors": "myorg/frontend"
    "#backend-errors": "myorg/backend"
    # Other channels use default_repo
```

## Network Security

### Required Outbound Connections

Allow only necessary outbound traffic:

| Service | Endpoints | Port |
|---------|-----------|------|
| Slack | `*.slack.com`, `wss://wss-primary.slack.com` | 443 |
| GitHub | `api.github.com`, `github.com` | 443 |
| OpenAI | `api.openai.com` | 443 |
| Anthropic | `api.anthropic.com` | 443 |
| Ollama | `localhost` (or configured host) | 11434 |

### SSRF Prevention

The agent includes built-in SSRF protection for Ollama:

```yaml
llm:
  ollama:
    # Only localhost allowed by default
    base_url: "http://localhost:11434"
    allow_remote_host: false  # Security default
    
    # To allow remote hosts (use with caution):
    # base_url: "http://internal-ollama.mycompany.com:11434"
    # allow_remote_host: true
```

**Warning:** Setting `allow_remote_host: true` disables SSRF protection. Only use with trusted internal networks.

### Container Network Isolation

```yaml
# docker-compose.yaml
services:
  ai-issue-agent:
    networks:
      - agent-network
    # Drop unnecessary capabilities
    cap_drop:
      - ALL
    # Read-only root filesystem
    read_only: true
    # Temp directories for runtime needs
    tmpfs:
      - /tmp:noexec,nosuid,nodev

networks:
  agent-network:
    driver: bridge
```

## Secret Redaction

### Automatic Redaction

AI Issue Agent automatically redacts 30+ secret patterns before:
- Sending data to LLM providers
- Creating GitHub issues
- Writing to logs

### Detected Secret Types

| Category | Examples |
|----------|----------|
| Slack | `xoxb-*`, `xoxp-*`, `xapp-*` |
| GitHub | `ghp_*`, `github_pat_*`, `gho_*` |
| AWS | `AKIA*`, AWS secret keys |
| OpenAI | `sk-*`, `sk-proj-*` |
| Anthropic | `sk-ant-*` |
| Database | Connection strings with passwords |
| Private Keys | PEM headers, PGP blocks |
| JWT | Base64-encoded tokens |
| Internal IPs | `10.*`, `172.16-31.*`, `192.168.*` |

### Custom Redaction Patterns

Add organization-specific patterns:

```python
from ai_issue_agent.utils.security import SecretRedactor

redactor = SecretRedactor(
    custom_patterns=[
        (r"mycompany-api-[a-z0-9]{32}", "MyCompany API key"),
        (r"internal-[a-z0-9]{16}", "Internal service token"),
    ]
)
```

### Testing Redaction

```python
from ai_issue_agent.utils.security import SecretRedactor

redactor = SecretRedactor()
text = "Token: xoxb-123-456-abc Connection: postgres://user:pass@host/db"
safe_text = redactor.redact(text)
print(safe_text)
# Output: Token: [REDACTED] Connection: [REDACTED]
```

## Audit Logging

### Security Events

The following security events are logged:

| Event | Description |
|-------|-------------|
| `secret_redacted` | Secret was found and redacted |
| `security_violation` | Security policy violation detected |
| `input_rejected` | Input rejected due to validation failure |
| `rate_limit_hit` | Rate limit encountered |

### Log Configuration

```yaml
logging:
  level: INFO
  format: json  # Structured for SIEM ingestion
  
  file:
    enabled: true
    path: "/var/log/ai-issue-agent/agent.log"
```

### Log Analysis

Monitor for security anomalies:

```bash
# Count secret redactions
jq 'select(.event == "secret_redacted")' agent.log | wc -l

# Find security violations
jq 'select(.event == "security_violation")' agent.log

# Track rate limit events
jq 'select(.event == "rate_limit_hit")' agent.log
```

## Security Scanning

### Dependency Scanning

```bash
# Scan dependencies for vulnerabilities
poetry run pip-audit

# Or with safety
pip install safety
safety check
```

### Code Scanning

```bash
# Static analysis
pip install bandit
bandit -r src/ -ll

# Type checking (catches some security issues)
poetry run mypy src/ai_issue_agent
```

### Container Scanning

```bash
# Scan container image
trivy image ghcr.io/jtdub/ai-issue-agent:latest

# Or with Grype
grype ghcr.io/jtdub/ai-issue-agent:latest
```

## Incident Response

### If Secrets Are Exposed

1. **Immediately rotate** the exposed credential
2. **Revoke** the old credential
3. **Delete** any GitHub issues containing secrets
4. **Review** logs for unauthorized access
5. **Update** secret detection patterns if needed
6. **Document** the incident

### Credential Rotation Commands

```bash
# Revoke and regenerate Slack tokens
# (Do this in Slack admin console)

# Regenerate GitHub token
gh auth refresh

# Rotate API keys
# (Do this in provider console)
```

### Reporting Security Issues

If you discover a security vulnerability:
1. **Do NOT** open a public GitHub issue
2. Email security concerns to the maintainers
3. Provide detailed reproduction steps
4. Allow 90 days for fix before public disclosure

## Security Checklist

Before production deployment:

- [ ] All credentials stored in environment variables or secrets manager
- [ ] Slack token scopes are minimal
- [ ] GitHub token uses fine-grained PAT with limited repos
- [ ] `allow_public_repos: false` unless explicitly needed
- [ ] `allow_remote_host: false` for Ollama
- [ ] JSON logging enabled for security monitoring
- [ ] Log aggregation configured
- [ ] Alerting on security events
- [ ] Regular credential rotation scheduled
- [ ] Dependency scanning in CI/CD
- [ ] Container scanning in CI/CD

For comprehensive security details, see [SECURITY.md](../SECURITY.md).
