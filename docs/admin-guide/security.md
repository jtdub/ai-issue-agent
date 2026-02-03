# Security

Security best practices and hardening guidelines.

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

- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault
- GCP Secret Manager

### Rotate Credentials Regularly

Set up automated rotation for:
- Slack tokens (90 days)
- GitHub tokens (90 days)
- LLM API keys (90 days)

## Access Control

### Principle of Least Privilege

Grant only necessary permissions:

**Slack:**
- `chat:write` (required)
- `reactions:write` (required)
- `channels:history` (required)
- ~~`admin`~~ (not needed)

**GitHub:**
- `repo` (required)
- ~~`admin:org`~~ (not needed)

### Repository Restrictions

```yaml
vcs:
  github:
    allowed_repos:
      - "myorg/app1"
      - "myorg/app2"
    allow_public_repos: false
```

## Network Security

### Firewall Rules

Allow only required outbound connections:
- Slack API: `*.slack.com:443`
- GitHub API: `api.github.com:443`
- LLM Provider: Provider-specific endpoints

### SSRF Prevention

Built-in protection prevents Server-Side Request Forgery:

```yaml
llm:
  ollama:
    base_url: "http://internal.server:11434"
    allow_remote_host: true  # Required for non-localhost
```

## Secret Redaction

The agent automatically redacts secrets before creating issues:

- API keys
- Passwords
- Tokens
- Private IPs
- Connection strings

Test redaction:
```bash
ai-issue-agent --test-redaction < test-input.txt
```

## Audit Logging

Enable comprehensive audit logs:

```yaml
logging:
  level: INFO
  audit:
    enabled: true
    events:
      - secret_detected
      - api_call
      - issue_created
      - error_occurred
```

## Security Scanning

Run security scans:

```bash
# Dependency scanning
pip-audit

# Code scanning
bandit -r src/

# Container scanning
trivy image ghcr.io/jtdub/ai-issue-agent:latest
```

## Incident Response

If secrets are exposed:

1. **Immediately rotate** the exposed credential
2. **Delete** the GitHub issue
3. **Review** logs for unauthorized access
4. **Update** secret patterns if needed
5. **Document** the incident

For comprehensive security guidelines, see [SECURITY.md](../reference/security.md).
