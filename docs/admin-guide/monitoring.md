# Monitoring

Comprehensive monitoring and observability for AI Issue Agent in production.

## Overview

AI Issue Agent provides built-in observability through:

- **Structured Logging** - JSON or console output with secret sanitization
- **Health Checks** - Verify all dependencies are operational
- **Metrics Collection** - Track message processing, issue creation, and errors
- **Context Correlation** - Request IDs and context propagation

## Health Checks

### CLI Health Check

```bash
# Run health check and exit
ai-issue-agent --config config.yaml --health-check

# Returns:
# - Exit code 0 if healthy
# - Exit code 1 if unhealthy
```

### Health Check Components

The health check verifies:

| Component | What it checks |
|-----------|----------------|
| Config | Valid configuration loaded |
| Slack | Bot and app tokens present and valid format |
| GitHub | `gh` CLI authenticated |
| LLM | API key configured |

### Programmatic Health Check

```python
from ai_issue_agent.utils.health import HealthChecker
from ai_issue_agent.config.loader import load_config

config = load_config("config.yaml")
checker = HealthChecker(config)
result = await checker.run_all_checks()

print(f"Healthy: {result.healthy}")
print(f"Status: {result.status}")
for check in result.checks:
    print(f"  {check.name}: {check.status} - {check.message}")
```

### Health Check Output

```json
{
  "healthy": true,
  "status": "healthy",
  "timestamp": "2026-02-04T12:00:00Z",
  "checks": [
    {"name": "config", "status": "healthy", "message": "Configuration valid"},
    {"name": "slack_tokens", "status": "healthy", "message": "Slack tokens configured"},
    {"name": "github_auth", "status": "healthy", "message": "GitHub CLI authenticated"},
    {"name": "llm_provider", "status": "healthy", "message": "Anthropic configured"}
  ],
  "details": {
    "total_checks": 4,
    "healthy_checks": 4,
    "degraded_checks": 0,
    "unhealthy_checks": 0
  }
}
```

## Structured Logging

### Configuration

```yaml
logging:
  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  level: INFO
  
  # Output format: json (for aggregation) or console (for development)
  format: json
  
  # Optional file logging
  file:
    enabled: true
    path: "/var/log/ai-issue-agent/agent.log"
    rotation: "10 MB"
    retention: 7  # days
```

### Log Format Selection

```bash
# JSON format (for production/log aggregation)
ai-issue-agent --format json

# Console format (for development)
ai-issue-agent --format console

# Debug mode
ai-issue-agent --debug
```

### Log Event Types

All significant events are logged with consistent event names:

| Event | Description |
|-------|-------------|
| `agent_starting` | Agent is starting up |
| `agent_started` | Agent successfully started |
| `agent_stopping` | Agent is shutting down |
| `message_received` | New message received from chat |
| `traceback_detected` | Traceback found in message |
| `traceback_not_found` | No traceback in message |
| `issue_search_start` | Starting issue search |
| `issue_matched` | Found matching existing issue |
| `issue_created` | New issue created |
| `llm_request_start` | LLM API request started |
| `llm_request_complete` | LLM API request completed |
| `rate_limit_hit` | API rate limit encountered |
| `secret_redacted` | Secret was redacted from content |
| `health_check_complete` | Health check finished |

### Log Example (JSON)

```json
{
  "event": "issue_created",
  "level": "info",
  "timestamp": "2026-02-04T12:00:00.000Z",
  "service": "ai-issue-agent",
  "version": "0.1.0",
  "channel_id": "C123ABC",
  "message_id": "1234567890.123456",
  "issue_url": "https://github.com/org/repo/issues/123",
  "processing_duration_ms": 2500
}
```

### Secret Sanitization

All log output is automatically sanitized to remove secrets:

```python
# Before sanitization
log.info("connecting", token="xoxb-123-secret-token")

# After sanitization (in output)
{"event": "connecting", "token": "[REDACTED]"}
```

Patterns detected and redacted:
- Slack tokens (`xoxb-*`, `xapp-*`)
- GitHub tokens (`ghp_*`, `github_pat_*`)
- API keys (OpenAI, Anthropic, AWS, etc.)
- Database connection strings
- Private keys
- JWT tokens

## Metrics Collection

### Built-in Metrics

AI Issue Agent collects these metrics internally:

```python
from ai_issue_agent.utils.metrics import get_metrics

metrics = get_metrics()
stats = metrics.get_all_metrics()

# Example output:
{
    "uptime_seconds": 3600.5,
    "messages": {
        "received": 150,
        "processed": 148,
        "errors": 2
    },
    "tracebacks": {
        "detected": 45
    },
    "issues": {
        "created": 12,
        "linked": 28,
        "searches": 45
    },
    "llm": {
        "requests": 45,
        "errors": 1,
        "tokens_used": 125000
    },
    "cache": {
        "hits": 30,
        "misses": 15
    },
    "processing": {
        "active_tasks": 2,
        "duration_stats": {
            "count": 148,
            "sum": 370.5,
            "min": 0.5,
            "max": 15.2,
            "mean": 2.5
        }
    }
}
```

### Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `messages_received` | Counter | Total messages received |
| `messages_processed` | Counter | Successfully processed messages |
| `messages_errors` | Counter | Processing errors |
| `tracebacks_detected` | Counter | Tracebacks found |
| `issues_created` | Counter | New issues created |
| `issues_linked` | Counter | Linked to existing issues |
| `llm_requests` | Counter | LLM API calls |
| `llm_tokens_used` | Counter | Total tokens consumed |
| `processing_duration` | Histogram | Processing time distribution |
| `cache_hits` / `cache_misses` | Counter | Cache efficiency |
| `rate_limits_hit` | Counter | Rate limits encountered |
| `secrets_redacted` | Counter | Secrets removed from content |
| `active_tasks` | Gauge | Currently processing tasks |

### Prometheus Format

Export metrics in Prometheus format:

```python
from ai_issue_agent.utils.metrics import get_metrics

metrics = get_metrics()
prometheus_output = metrics.to_prometheus_format()
print(prometheus_output)
```

Output:
```
# HELP ai_issue_agent_messages_processed_total Total messages successfully processed
# TYPE ai_issue_agent_messages_processed_total counter
ai_issue_agent_messages_processed_total 148

# HELP ai_issue_agent_issues_created_total Total issues created on VCS
# TYPE ai_issue_agent_issues_created_total counter
ai_issue_agent_issues_created_total 12

# HELP ai_issue_agent_active_tasks Number of currently processing tasks
# TYPE ai_issue_agent_active_tasks gauge
ai_issue_agent_active_tasks 2

# HELP ai_issue_agent_uptime_seconds Agent uptime in seconds
# TYPE ai_issue_agent_uptime_seconds gauge
ai_issue_agent_uptime_seconds 3600.5
```

## Alerting

### Recommended Alerts

Configure alerts for these conditions:

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Error Rate | `errors / processed > 5%` | Warning |
| Health Check Failed | Exit code 1 | Critical |
| Rate Limit Exceeded | `rate_limits_hit` increasing | Warning |
| Long Processing Time | `processing_duration > 5min` | Warning |
| No Messages Processed | 0 messages in 1 hour | Info |

### Prometheus Alert Rules

```yaml
groups:
  - name: ai-issue-agent
    rules:
      - alert: AIIssueAgentHighErrorRate
        expr: rate(ai_issue_agent_messages_errors_total[5m]) / rate(ai_issue_agent_messages_processed_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in AI Issue Agent"
          description: "Error rate is {{ $value | humanizePercentage }}"
      
      - alert: AIIssueAgentUnhealthy
        expr: ai_issue_agent_health_status == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "AI Issue Agent is unhealthy"
      
      - alert: AIIssueAgentRateLimited
        expr: increase(ai_issue_agent_rate_limits_hit_total[5m]) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "AI Issue Agent hitting rate limits"
      
      - alert: AIIssueAgentSlowProcessing
        expr: histogram_quantile(0.95, ai_issue_agent_processing_duration_seconds_bucket) > 300
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "AI Issue Agent processing is slow"
```

## Log Aggregation

### Fluentd Configuration

```xml
<source>
  @type tail
  path /var/log/ai-issue-agent/agent.log
  pos_file /var/log/fluentd/ai-issue-agent.pos
  tag ai-issue-agent
  <parse>
    @type json
    time_key timestamp
  </parse>
</source>

<filter ai-issue-agent>
  @type record_transformer
  <record>
    hostname "#{Socket.gethostname}"
  </record>
</filter>

<match ai-issue-agent>
  @type elasticsearch
  host elasticsearch.example.com
  port 9200
  index_name ai-issue-agent
</match>
```

### Loki + Promtail

```yaml
# promtail-config.yaml
scrape_configs:
  - job_name: ai-issue-agent
    static_configs:
      - targets:
          - localhost
        labels:
          job: ai-issue-agent
          __path__: /var/log/ai-issue-agent/agent.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            event: event
            service: service
      - labels:
          level:
          event:
          service:
```

## Docker Health Checks

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ai-issue-agent --config /app/config.yaml --health-check
```

```yaml
# docker-compose.yaml
services:
  ai-issue-agent:
    healthcheck:
      test: ["CMD", "ai-issue-agent", "--config", "/app/config.yaml", "--health-check"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## Kubernetes Probes

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: ai-issue-agent
          livenessProbe:
            exec:
              command:
                - ai-issue-agent
                - --config
                - /app/config.yaml
                - --health-check
            initialDelaySeconds: 30
            periodSeconds: 30
          readinessProbe:
            exec:
              command:
                - ai-issue-agent
                - --config
                - /app/config.yaml
                - --health-check
            initialDelaySeconds: 10
            periodSeconds: 10
```

## Dashboards

### Key Dashboard Panels

1. **Message Processing**
   - Messages received/processed/errors over time
   - Processing duration histogram
   - Active tasks gauge

2. **Issue Operations**
   - Issues created vs linked ratio
   - Issue search latency

3. **LLM Usage**
   - API requests and errors
   - Token consumption
   - Request latency

4. **System Health**
   - Health check status
   - Uptime
   - Cache hit ratio

### Grafana Dashboard JSON

See `monitoring/grafana-dashboard.json` for a pre-built dashboard.
