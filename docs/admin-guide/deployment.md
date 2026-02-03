# Deployment

Production deployment strategies for AI Issue Agent.

## Docker Deployment (Recommended)

### Dockerfile

Create `Dockerfile`:

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
    apt-get install -y gh

# Create non-root user
RUN useradd -m -u 1000 agent

# Install application
WORKDIR /app
COPY pyproject.toml /app/
RUN pip install --no-cache-dir ai-issue-agent

# Switch to non-root user
USER agent

# Run application
CMD ["ai-issue-agent", "--config", "/app/config.yaml"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  ai-issue-agent:
    build: .
    container_name: ai-issue-agent
    restart: unless-stopped
    
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./repos:/tmp/ai-issue-agent/repos
      - ./logs:/var/log/ai-issue-agent
    
    environment:
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
      - SLACK_APP_TOKEN=${SLACK_APP_TOKEN}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    
    mem_limit: 2g
    cpus: 2
    
    healthcheck:
      test: ["CMD", "pgrep", "-f", "ai-issue-agent"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Deploy

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Stop
docker-compose down
```

## Systemd Service

### Service File

Create `/etc/systemd/system/ai-issue-agent.service`:

```ini
[Unit]
Description=AI Issue Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ai-issue-agent
Group=ai-issue-agent
WorkingDirectory=/opt/ai-issue-agent
Environment="PATH=/opt/ai-issue-agent/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/etc/ai-issue-agent/environment
ExecStart=/opt/ai-issue-agent/venv/bin/ai-issue-agent --config /etc/ai-issue-agent/config.yaml

# Restart configuration
Restart=on-failure
RestartSec=10s
StartLimitBurst=3
StartLimitInterval=60s

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/ai-issue-agent /tmp/ai-issue-agent
CapabilityBoundingSet=
SystemCallFilter=@system-service
SystemCallArchitectures=native

# Resource limits
LimitNOFILE=65536
MemoryMax=2G
CPUQuota=200%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ai-issue-agent

[Install]
WantedBy=multi-user.target
```

### Environment File

Create `/etc/ai-issue-agent/environment`:

```bash
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_APP_TOKEN=xapp-your-token
GITHUB_TOKEN=ghp_your-token
ANTHROPIC_API_KEY=sk-ant-your-key
```

### Deploy

```bash
# Set permissions
sudo chmod 600 /etc/ai-issue-agent/environment
sudo chown root:root /etc/ai-issue-agent/environment

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable ai-issue-agent
sudo systemctl start ai-issue-agent

# Check status
sudo systemctl status ai-issue-agent

# View logs
sudo journalctl -u ai-issue-agent -f
```

## Kubernetes Deployment

### Deployment Manifest

Create `k8s-deployment.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ai-issue-agent

---
apiVersion: v1
kind: Secret
metadata:
  name: ai-issue-agent-secrets
  namespace: ai-issue-agent
type: Opaque
stringData:
  SLACK_BOT_TOKEN: "xoxb-your-token"
  SLACK_APP_TOKEN: "xapp-your-token"
  GITHUB_TOKEN: "ghp_your-token"
  ANTHROPIC_API_KEY: "sk-ant-your-key"

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: ai-issue-agent-config
  namespace: ai-issue-agent
data:
  config.yaml: |
    # Your configuration here

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-issue-agent
  namespace: ai-issue-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ai-issue-agent
  template:
    metadata:
      labels:
        app: ai-issue-agent
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      
      containers:
      - name: ai-issue-agent
        image: ghcr.io/jtdub/ai-issue-agent:latest
        imagePullPolicy: Always
        
        envFrom:
        - secretRef:
            name: ai-issue-agent-secrets
        
        volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
        - name: repos
          mountPath: /tmp/ai-issue-agent/repos
        
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        
        livenessProbe:
          exec:
            command:
            - pgrep
            - -f
            - ai-issue-agent
          initialDelaySeconds: 30
          periodSeconds: 30
        
        readinessProbe:
          exec:
            command:
            - pgrep
            - -f
            - ai-issue-agent
          initialDelaySeconds: 10
          periodSeconds: 10
      
      volumes:
      - name: config
        configMap:
          name: ai-issue-agent-config
      - name: repos
        emptyDir:
          sizeLimit: 10Gi

---
apiVersion: v1
kind: Service
metadata:
  name: ai-issue-agent
  namespace: ai-issue-agent
spec:
  selector:
    app: ai-issue-agent
  ports:
  - port: 8080
    targetPort: 8080
```

### Deploy

```bash
# Apply manifests
kubectl apply -f k8s-deployment.yaml

# Check status
kubectl get pods -n ai-issue-agent
kubectl logs -f -n ai-issue-agent deployment/ai-issue-agent

# Scale
kubectl scale deployment ai-issue-agent --replicas=2 -n ai-issue-agent
```

## Cloud Platforms

### AWS ECS

```json
{
  "family": "ai-issue-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "ai-issue-agent",
      "image": "ghcr.io/jtdub/ai-issue-agent:latest",
      "secrets": [
        {
          "name": "SLACK_BOT_TOKEN",
          "valueFrom": "arn:aws:secretsmanager:..."
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ai-issue-agent",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Google Cloud Run

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ai-issue-agent
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "3"
    spec:
      containers:
      - image: gcr.io/project/ai-issue-agent:latest
        env:
        - name: SLACK_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: slack-credentials
              key: bot-token
        resources:
          limits:
            memory: 2Gi
            cpu: "2"
```

## Configuration Management

### HashiCorp Vault Integration

```yaml
# vault-config.hcl
path "secret/data/ai-issue-agent/*" {
  capabilities = ["read"]
}
```

```bash
# Retrieve secrets
export SLACK_BOT_TOKEN=$(vault kv get -field=bot_token secret/ai-issue-agent/slack)
export GITHUB_TOKEN=$(vault kv get -field=token secret/ai-issue-agent/github)
```

### AWS Secrets Manager

```bash
# Store secrets
aws secretsmanager create-secret \
  --name ai-issue-agent/slack-bot-token \
  --secret-string "xoxb-your-token"

# Retrieve in config
SLACK_BOT_TOKEN=$(aws secretsmanager get-secret-value \
  --secret-id ai-issue-agent/slack-bot-token \
  --query SecretString --output text)
```

## Health Checks

Add health check endpoint in your deployment:

```yaml
healthcheck:
  endpoint: /health
  interval: 30s
  timeout: 5s
  retries: 3
```

## Backup Strategy

```bash
# Backup configuration
tar -czf backup-$(date +%Y%m%d).tar.gz \
  /etc/ai-issue-agent/config.yaml \
  /var/log/ai-issue-agent

# Automated daily backup
cat > /etc/cron.daily/ai-issue-agent-backup << 'EOF'
#!/bin/bash
tar -czf /backups/ai-issue-agent-$(date +%Y%m%d).tar.gz \
  /etc/ai-issue-agent
find /backups -name "ai-issue-agent-*.tar.gz" -mtime +30 -delete
EOF
chmod +x /etc/cron.daily/ai-issue-agent-backup
```

## Rolling Updates

### Docker Compose

```bash
# Pull new image
docker-compose pull

# Recreate containers
docker-compose up -d --no-deps --build
```

### Kubernetes

```bash
# Update image
kubectl set image deployment/ai-issue-agent \
  ai-issue-agent=ghcr.io/jtdub/ai-issue-agent:v0.2.0 \
  -n ai-issue-agent

# Watch rollout
kubectl rollout status deployment/ai-issue-agent -n ai-issue-agent

# Rollback if needed
kubectl rollout undo deployment/ai-issue-agent -n ai-issue-agent
```

## Next Steps

- [Monitoring Setup](monitoring.md)
- [Security Hardening](security.md)
- [Performance Tuning](performance.md)
