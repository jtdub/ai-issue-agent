# Performance Tuning

Optimize AI Issue Agent for your workload.

## Concurrency Tuning

Adjust concurrent processing:

```yaml
runtime:
  max_concurrent: 5  # Start here
  processing_timeout: 300
```

Guidelines:
- **Low volume** (<10/hour): `max_concurrent: 2-3`
- **Medium volume** (10-50/hour): `max_concurrent: 5-10`
- **High volume** (>50/hour): `max_concurrent: 10-20`

Monitor CPU and memory usage to find optimal settings.

## LLM Optimization

### Model Selection

Choose based on speed vs quality:

```yaml
# Fastest (good for high volume)
llm:
  anthropic:
    model: "claude-3-haiku-20240307"

# Balanced (recommended)
llm:
  anthropic:
    model: "claude-3-sonnet-20240229"

# Best quality (slower)
llm:
  anthropic:
    model: "claude-3-opus-20240229"
```

### Token Limits

Reduce tokens for faster responses:

```yaml
llm:
  anthropic:
    max_tokens: 2048  # Default: 4096
```

## Cache Optimization

Tune cache settings:

```yaml
matching:
  search_cache_ttl: 300  # 5 minutes

data_retention:
  clone_cache:
    max_age_hours: 12  # Reduce for faster updates
    max_total_size_gb: 5
```

## Resource Limits

### Memory

```yaml
# Docker
mem_limit: 2g

# Kubernetes
resources:
  limits:
    memory: "2Gi"
```

### CPU

```yaml
# Docker
cpus: 2

# Kubernetes
resources:
  limits:
    cpu: "2000m"
```

## Scaling Strategies

### Vertical Scaling

Increase resources for single instance:
- More CPU for faster processing
- More memory for larger context
- Faster disk for clone operations

### Horizontal Scaling

Run multiple instances (requires work queue):
- Use message broker (Redis/RabbitMQ)
- Implement distributed locking
- Share clone cache

## Benchmarking

Run performance tests:

```bash
# Process test messages
ai-issue-agent --benchmark --messages 100

# Profile resource usage
/usr/bin/time -v ai-issue-agent --config config.yaml
```

For more optimization techniques, see the [Administrator Guide](overview.md).
