# Monitoring

Comprehensive monitoring setup for AI Issue Agent in production.

## Metrics

Key metrics to track:

- **Processing Rate**: Messages processed per minute
- **Success Rate**: Percentage of successful issue creations
- **Processing Duration**: Time to process each message
- **API Latency**: Response time from external APIs
- **Error Rate**: Errors per hour by type
- **Resource Usage**: CPU, memory, disk usage
- **Queue Depth**: Pending messages

## Prometheus Integration

Configure Prometheus scraping in `config.yaml`:

```yaml
monitoring:
  enabled: true
  port: 9090
  path: /metrics
```

Metrics exposed:

```
# Message processing
ai_issue_agent_messages_processed_total
ai_issue_agent_messages_failed_total
ai_issue_agent_processing_duration_seconds

# API calls
ai_issue_agent_api_calls_total{provider="slack|github|openai"}
ai_issue_agent_api_latency_seconds{provider="..."}
ai_issue_agent_api_errors_total{provider="...",error_type="..."}

# Resource usage
ai_issue_agent_memory_bytes
ai_issue_agent_cpu_seconds_total
ai_issue_agent_clone_cache_size_bytes
```

## Grafana Dashboard

Import the pre-built dashboard from `monitoring/grafana-dashboard.json`.

## Log Aggregation

Configure structured logging for aggregation:

```yaml
logging:
  level: INFO
  format: json
  
  outputs:
    - type: file
      path: /var/log/ai-issue-agent/agent.log
    - type: syslog
      host: localhost
      port: 514
```

## Alerting Rules

Example Prometheus alerts:

```yaml
groups:
- name: ai-issue-agent
  rules:
  - alert: HighErrorRate
    expr: rate(ai_issue_agent_messages_failed_total[5m]) > 0.1
    for: 5m
    annotations:
      summary: "High error rate detected"
  
  - alert: ProcessingSlowdown
    expr: ai_issue_agent_processing_duration_seconds > 300
    for: 10m
    annotations:
      summary: "Processing taking too long"
```

For detailed monitoring setup, see the [Administrator Guide](overview.md).
