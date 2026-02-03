# Troubleshooting

Common issues and their solutions.

## Agent Won't Start

### Problem: Configuration validation fails

```
Error: Invalid configuration: chat.slack.bot_token is required
```

**Solution:**
- Verify all required environment variables are set
- Check that config.yaml references them correctly:
```yaml
bot_token: ${SLACK_BOT_TOKEN}  # Not: ${SLACK_TOKEN}
```
- Test environment variable substitution:
```bash
envsubst < config.yaml
```

### Problem: Cannot connect to Slack

```
Error: slack.errors.SlackApiError: invalid_auth
```

**Solution:**
- Verify bot token is correct and hasn't expired
- Check token format (should start with `xoxb-`)
- Ensure app is installed to workspace
- Re-authenticate:
```bash
# Get fresh token from Slack App settings
export SLACK_BOT_TOKEN="xoxb-new-token"
```

### Problem: GitHub authentication fails

```
Error: gh: authentication failed
```

**Solution:**
- Authenticate GitHub CLI:
```bash
gh auth login
```
- Or set token directly:
```bash
export GITHUB_TOKEN="ghp_your_token"
```
- Verify token permissions include `repo` scope

## Processing Issues

### Problem: Messages not being processed

**Check list:**
1. Is the bot invited to the channel?
```bash
# In Slack, type: /invite @your-bot-name
```

2. Are you monitoring the right channels?
```yaml
channels:
  - "#errors"  # Must match exact channel name
```

3. Check logs for errors:
```bash
tail -f /var/log/ai-issue-agent/agent.log
```

### Problem: No reaction added to messages

**Solution:**
- Verify `reactions:write` OAuth scope is enabled
- Check bot permissions in channel
- Look for rate limiting in logs

### Problem: Duplicate issues created

**Solution:**
- Lower confidence threshold:
```yaml
matching:
  confidence_threshold: 0.75  # Was 0.85
```
- Increase search results:
```yaml
matching:
  max_search_results: 50  # Was 20
```
- Clear search cache:
```bash
rm -rf /tmp/ai-issue-agent/cache
```

## LLM Provider Issues

### Problem: OpenAI rate limits

```
Error: Rate limit exceeded
```

**Solution:**
- Reduce concurrency:
```yaml
runtime:
  max_concurrent: 2  # Was 5
```
- Add retry configuration:
```yaml
runtime:
  retry:
    max_attempts: 5
    max_delay: 60.0
```
- Upgrade OpenAI tier or wait

### Problem: Anthropic timeout

```
Error: Request timeout after 60s
```

**Solution:**
- Increase timeout:
```yaml
llm:
  anthropic:
    timeout: 120  # Seconds
```
- Use smaller model:
```yaml
llm:
  anthropic:
    model: "claude-3-haiku-20240307"  # Faster
```

### Problem: Ollama connection refused

```
Error: Connection refused to localhost:11434
```

**Solution:**
- Start Ollama:
```bash
ollama serve
```
- Check if running:
```bash
curl http://localhost:11434/api/tags
```
- Verify model is pulled:
```bash
ollama list
ollama pull llama2:70b
```

## GitHub Issues

### Problem: Issues not created

**Check:**
1. Repository exists and is accessible
2. Token has `repo` permission
3. Repository isn't archived
4. Not hitting API rate limit

```bash
# Test manually
gh issue create --repo myorg/myrepo --title "Test" --body "Test"
```

### Problem: Labels not applied

**Solution:**
- Create labels first:
```bash
gh label create auto-triaged --repo myorg/myrepo
gh label create needs-review --repo myorg/myrepo
```
- Or disable labeling:
```yaml
vcs:
  github:
    default_labels: []
```

## Performance Issues

### Problem: Slow processing

**Diagnostics:**
```bash
# Check logs for bottlenecks
grep "duration" /var/log/ai-issue-agent/agent.log

# Monitor system resources
top
df -h /tmp/ai-issue-agent
```

**Solutions:**
- Increase timeout:
```yaml
runtime:
  processing_timeout: 600  # Was 300
```
- Reduce context:
```yaml
analysis:
  context_lines: 10  # Was 15
  max_files: 5       # Was 10
```
- Clean up clones:
```bash
rm -rf /tmp/ai-issue-agent/repos/*
```

### Problem: High memory usage

**Solution:**
- Reduce concurrent processing:
```yaml
runtime:
  max_concurrent: 3  # Was 5
```
- Enable cache cleanup:
```yaml
data_retention:
  clone_cache:
    max_age_hours: 12  # Was 24
    max_total_size_gb: 5  # Was 10
```

## Security Issues

### Problem: Secrets appearing in issues

**Immediate action:**
1. Delete the GitHub issue
2. Rotate any exposed credentials
3. Review and update secret patterns in SECURITY.md

**Prevention:**
- Test secret redaction:
```bash
echo "OPENAI_API_KEY=sk-abc123" | ai-issue-agent --test-redaction
```
- Review patterns:
```python
from ai_issue_agent.utils.security import SecretRedactor
redactor = SecretRedactor()
print(redactor.patterns)
```

### Problem: SSRF attempt blocked

```
Error: Ollama URL rejected (SSRF prevention)
```

**Solution (if intentional):**
```yaml
llm:
  ollama:
    allow_remote_host: true  # Be careful!
    base_url: "http://ollama.internal:11434"
```

## Debugging

### Enable debug logging

```yaml
logging:
  level: DEBUG
```

Or via command line:
```bash
ai-issue-agent --config config.yaml --log-level DEBUG
```

### Test specific message

```bash
# Replay a specific Slack message
ai-issue-agent --config config.yaml \
  --process-url "https://workspace.slack.com/archives/C123/p1234567890"
```

### Validate configuration

```bash
ai-issue-agent --config config.yaml --validate
```

### Check version

```bash
ai-issue-agent --version
```

## Getting Help

### Collect diagnostic information

```bash
# System information
uname -a
python --version
ai-issue-agent --version

# Configuration (redacted)
ai-issue-agent --config config.yaml --dump-config | sed 's/token.*/token: [REDACTED]/'

# Recent logs
tail -n 100 /var/log/ai-issue-agent/agent.log
```

### Report an issue

When reporting issues, include:

1. AI Issue Agent version
2. Python version
3. Operating system
4. Configuration (with secrets redacted)
5. Full error message and stack trace
6. Steps to reproduce

File issues at: [github.com/jtdub/ai-issue-agent/issues](https://github.com/jtdub/ai-issue-agent/issues)

### Community support

- **GitHub Discussions**: [github.com/jtdub/ai-issue-agent/discussions](https://github.com/jtdub/ai-issue-agent/discussions)
- **Documentation**: [jtdub.github.io/ai-issue-agent](https://jtdub.github.io/ai-issue-agent)

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid configuration` | Missing required fields | Check config.yaml against example |
| `Authentication failed` | Invalid token | Regenerate and update token |
| `Rate limit exceeded` | Too many API calls | Reduce concurrency or wait |
| `Repository not found` | Invalid repo name | Verify repo exists and is accessible |
| `Connection refused` | Service not running | Start the required service |
| `Timeout` | Operation too slow | Increase timeout or optimize |
| `Permission denied` | Insufficient permissions | Add required OAuth scopes |
