<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Runbook: Service Down

## Alert Details

**Alert Names:**
- `MongoDBDown`
- `RabbitMQDown`
- `QdrantDown`
- `OllamaDown`
- `ProcessingServiceUnhealthy`
- `NoQueueConsumers`

**Severity:** Warning → Critical  
**Component:** Infrastructure / Services

---

## Symptoms

- Service container not running or unhealthy
- Health check failures
- No metrics received from service
- Queue has no consumers
- Connection errors in dependent services

**User Impact:**
- **MongoDB down**: Cannot read/write documents (CRITICAL)
- **RabbitMQ down**: No message processing (CRITICAL)
- **Qdrant down**: Cannot generate/search embeddings (HIGH)
- **Ollama down**: Summarization degraded (MEDIUM)
- **Processing service down**: Pipeline stalled (HIGH)

---

## Diagnosis

### 1. Check Service Status

```bash
# Check all services
docker compose ps

# Check specific service
docker compose ps <service_name>

# Expected output: "Up (healthy)" or "Up (health: starting)"
# Problem indicators: "Exit", "Restarting", "Up (unhealthy)"
```

### 2. Check Service Logs

```bash
# View recent logs
docker compose logs <service_name> --tail=100

# Follow logs in real-time
docker compose logs <service_name> -f

# Look for:
# - Startup errors
# - Connection failures
# - OOM (Out of Memory) messages
# - Crash stack traces
```

### 3. Check Resource Usage

```bash
# Check container resource usage
docker stats <service_name>

# Check system resources (Linux/macOS)
df -h                # Disk space
free -h              # Memory
top                  # CPU usage

# Windows PowerShell alternative for disk space
# Get-PSDrive C | Select-Object Used,Free,@{Name="Size";Expression={$_.Used+$_.Free}}
```

### 4. Check Health Endpoint (if applicable)

```bash
# MongoDB
docker compose exec documentdb mongosh --eval "db.adminCommand('ping')"

# RabbitMQ
curl -u guest:guest http://localhost:15672/api/health/checks/alarms

# Qdrant
curl http://localhost:6333/collections

# Ollama
curl http://localhost:11434/api/tags

# Service health endpoints
curl http://localhost:<port>/health
```

---

## Root Causes

### Cause 1: Container Crash

**Symptoms:**
- Service container exited
- Exit code visible in `docker compose ps`
- Crash logs in `docker compose logs`

**Common Exit Codes:**
- `0`: Clean exit (expected)
- `1`: Application error
- `137`: OOM killed (out of memory)
- `139`: Segmentation fault
- `143`: SIGTERM (graceful shutdown)

**Fix:**
```bash
# Check logs for crash reason
docker compose logs <service_name> --tail=200 | grep -i -E "error|exception|fatal|killed"

# Check for OOM
dmesg | grep -i "out of memory"

# Restart service
docker compose restart <service_name>

# If OOM, increase memory limit in docker-compose.yml
```

### Cause 2: Health Check Failure

**Symptoms:**
- Container running but health check fails
- Status shows "Up (unhealthy)"
- Health check command timing out

**Fix:**
```bash
# Check health check configuration
docker compose config | grep -A 5 "healthcheck:"

# Manually run health check command
docker compose exec <service_name> <health_check_command>

# If health check is too strict, adjust interval/timeout
# Edit docker-compose.yml:
healthcheck:
  interval: 30s       # Increase if service is slow to start
  timeout: 10s        # Increase if health check is slow
  retries: 5          # Increase for more tolerance
  start_period: 60s   # Increase for services with long startup
```

### Cause 3: Dependency Failure

**Symptoms:**
- Service crashes on startup
- Connection errors in logs
- "Waiting for dependency" messages

**Fix:**
```bash
# Check dependencies are healthy
docker compose ps

# Restart in dependency order
docker compose restart documentdb messagebus vectorstore
sleep 30
docker compose restart <service_name>

# Verify service starts successfully
docker compose logs <service_name> -f
```

### Cause 4: Configuration Error

**Symptoms:**
- Service exits immediately on startup
- Configuration validation errors
- Missing environment variables

**Fix:**
```bash
# Check environment variables
docker compose exec <service_name> env | grep -i <VAR>

# Validate configuration files
# For Prometheus:
docker compose exec monitoring promtool check config /etc/prometheus/prometheus.yml

# For services, check application logs for config errors
docker compose logs <service_name> | grep -i config
```

### Cause 5: Resource Exhaustion

**Symptoms:**
- OOM kills (exit code 137)
- Disk full errors
- CPU throttling

**Fix:**
```bash
# Check disk space (Linux/macOS)
df -h
# Windows PowerShell: Get-PSDrive C | Select-Object Used,Free,@{Name="Size";Expression={$_.Used+$_.Free}}

# Free up space if needed:
docker system prune -a --volumes  # WARNING: Removes unused resources

# Check memory
free -h
# Increase swap if needed

# Increase service limits (docker-compose.yml):
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
```

---

## Resolution Steps

### Infrastructure Services (MongoDB, RabbitMQ, Qdrant)

#### MongoDB

```bash
# 1. Check status
docker compose ps documentdb

# 2. Check logs
docker compose logs documentdb --tail=100

# 3. Restart
docker compose restart documentdb

# 4. Wait for healthy status
docker compose ps documentdb
# Should show: "Up (healthy)"

# 5. Verify connectivity
docker compose exec documentdb mongosh --eval "db.adminCommand('ping')"

# 6. If still failing, check data volume
docker volume inspect <project>_mongo_data
```

#### RabbitMQ

```bash
# 1. Check status
docker compose ps messagebus

# 2. Check logs
docker compose logs messagebus --tail=100

# 3. Check for memory/disk alarms
curl -u guest:guest http://localhost:15672/api/health/checks/alarms

# 4. Restart
docker compose restart messagebus

# 5. Verify management UI
curl -u guest:guest http://localhost:15672/api/overview

# 6. If queues are stuck, may need to purge:
# rabbitmqctl purge_queue <queue_name>  # CAREFUL: Data loss
```

#### Qdrant

```bash
# 1. Check status
docker compose ps vectorstore

# 2. Check logs
docker compose logs vectorstore --tail=100

# 3. Check disk space (Linux/macOS)
df -h | grep qdrant
# Windows PowerShell: Get-PSDrive C | Select-Object Used,Free,@{Name="Size";Expression={$_.Used+$_.Free}}

# 4. Restart
docker compose restart vectorstore

# 5. Verify collections
curl http://localhost:6333/collections

# 6. If corrupted, may need to rebuild:
# docker compose down vectorstore
# docker volume rm <project>_vector_data  # CAREFUL: Data loss
# docker compose up -d vectorstore
```

### Processing Services (Parsing, Chunking, Embedding, etc.)

```bash
# 1. Check service status
docker compose ps <service_name>

# 2. Check logs for errors
docker compose logs <service_name> --tail=100

# 3. Check dependencies are healthy
docker compose ps documentdb messagebus vectorstore

# 4. Restart service
docker compose restart <service_name>

# 5. Verify consumer connects to queue
curl -u guest:guest http://localhost:15672/api/queues | jq ".[] | select(.name==\"<queue>\") | .consumers"

# 6. Check metrics emission
curl http://pushgateway:9091/metrics | grep <service_name>

# 7. If still failing, rebuild and restart
docker compose up -d --build <service_name>
```

---

## Verification

After restart, verify:

```bash
# 1. Container is running and healthy
docker compose ps <service_name>
# Expected: "Up (healthy)"

# 2. No errors in logs
docker compose logs <service_name> --since 5m | grep -i error
# Expected: No recent errors

# 3. Health endpoint responds
curl http://localhost:<port>/health
# Expected: HTTP 200

# 4. Consumers reconnected (for processing services)
curl -u guest:guest http://localhost:15672/api/queues/<queue> | jq ".consumers"
# Expected: >= 1

# 5. Metrics are flowing
curl http://localhost:9090/api/v1/query?query=up{job="<service>"}
# Expected: {"value": [<timestamp>, "1"]}
```

---

## Escalation

### When to Escalate

- Service won't start after restart
- Data corruption suspected
- Repeated crashes (> 3 in 1 hour)
- Infrastructure down for > 15 minutes
- Cannot determine root cause

### Who to Contact

1. **DevOps Team** - Infrastructure issues
2. **Database Admin** - MongoDB/data issues
3. **On-Call Engineer** - After hours (PagerDuty)
4. **Vendor Support** - Third-party service issues

### Incident Severity

- **P1 (Critical)**: MongoDB/RabbitMQ down, data loss risk
- **P2 (Error)**: Processing service down, SLO breach
- **P3 (Warning)**: Non-critical service down, degraded functionality

---

## Prevention

### Health Checks

Ensure all services have proper health checks:

```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:<port>/health || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

### Resource Limits

Set appropriate limits to prevent resource exhaustion:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

### Dependency Ordering

Use `depends_on` with health checks:

```yaml
depends_on:
  documentdb:
    condition: service_healthy
  messagebus:
    condition: service_healthy
```

### Auto-Restart

Configure restart policy:

```yaml
restart: unless-stopped
```

### Monitoring

- Set up alerts for service health
- Monitor resource usage trends
- Track restart frequency
- Log aggregation for error patterns

---

## Related

- **Dashboards**: [System Health](http://localhost:8080/grafana/d/system-health)
- **Alerts**: See `infra/prometheus/alerts/service_health.yml`
- **Docs**: [SERVICE_MONITORING.md](../SERVICE_MONITORING.md)
- **Architecture**: [DOCKER_COMPOSE_STRUCTURE.md](../DOCKER_COMPOSE_STRUCTURE.md)

---

## Post-Incident

1. **Document root cause** in incident log
2. **Update health checks** if inadequate
3. **Increase resource limits** if OOM
4. **Fix code bugs** if application crash
5. **Improve monitoring** to detect earlier
6. **Schedule postmortem** if P1/P2 incident
