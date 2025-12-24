<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Runbook: High Queue Lag

## Alert Details

**Alert Names:**
- `ParsingQueueDepthHigh` / `ParsingQueueDepthCritical`
- `ChunkingQueueDepthHigh`
- `EmbeddingQueueDepthHigh` / `EmbeddingQueueDepthCritical`
- `SummarizationQueueDepthHigh`
- `QueueMessageAgeHigh` / `QueueMessageAgeCritical`

**Severity:** Warning → Critical  
**Component:** Message Bus (RabbitMQ)

---

## Symptoms

- Queue depth exceeds threshold (100-1000+ messages)
- Oldest message age exceeds SLO (5-30+ minutes)
- Messages accumulating faster than processing
- Dashboard shows growing queue depth trend

**User Impact:**
- Delayed processing of ingested archives
- Slower time-to-summary for new content
- Reduced system throughput

---

## Diagnosis

### 1. Check Queue Status

Open RabbitMQ Management UI:
```bash
# Open in browser
http://localhost:15672

# Or check via API
curl -u guest:guest http://localhost:15672/api/queues
```

Look for:
- **Ready messages**: Count of pending messages
- **Consumer count**: Number of active consumers
- **Message rates**: Incoming vs. outgoing rates
- **Message age**: How long oldest message has waited

### 2. Check Service Health

```bash
# Check if service is running
docker compose ps <service_name>

# Check logs for errors
docker compose logs <service_name> --tail=100 | grep -i error

# Check resource usage
docker stats <service_name>
```

### 3. Check Processing Metrics

In Prometheus (http://localhost:9090):

```promql
# Processing throughput (messages/sec)
rate(copilot_<service>_messages_processed_total[5m])

# P95 processing latency
histogram_quantile(0.95, rate(copilot_<service>_processing_duration_seconds_bucket[5m]))

# Error rate
rate(copilot_<service>_failures_total[5m]) / rate(copilot_<service>_messages_processed_total[5m])
```

### 4. Check Dependencies

Verify dependent services are healthy:

```bash
# For parsing: Check MongoDB
docker compose ps documentdb
curl -s http://localhost:27017 || echo "MongoDB unreachable"

# For embedding: Check Ollama and Qdrant
docker compose ps ollama vectorstore
curl http://localhost:11434/api/tags
curl http://localhost:6333/collections
```

---

## Root Causes

### Cause 1: Service Not Processing (Consumer Down)

**Symptoms:**
- Consumer count = 0 on queue
- Service container stopped or restarting
- No metrics emitted from service

**Fix:**
```bash
# Restart service
docker compose restart <service_name>

# Verify consumer reconnects
watch -n 2 'curl -u guest:guest http://localhost:15672/api/queues | jq ".[] | select(.name==\"<queue>\") | .consumers"'
```

### Cause 2: Slow Processing (High Latency)

**Symptoms:**
- Consumer count > 0 but low throughput
- P95 latency exceeds target
- High CPU or memory usage

**Fix:**
```bash
# Scale service horizontally
docker compose up -d --scale <service_name>=3

# Monitor throughput improvement
watch -n 5 'docker compose exec monitoring promtool query instant "rate(copilot_<service>_messages_processed_total[5m])"'
```

### Cause 3: Ingestion Burst (Temporary)

**Symptoms:**
- Queue depth spiked recently
- Ingestion rate temporarily exceeded processing capacity
- Queue is draining (depth decreasing)

**Action:**
- Monitor queue drain rate
- No immediate action needed if draining
- Consider pre-scaling if burst is predictable

### Cause 4: Dependency Failure

**Symptoms:**
- High error rate from service
- Failed queue accumulating messages
- Dependency (MongoDB/Qdrant/Ollama) unhealthy

**Fix:**
```bash
# Check dependency health
docker compose ps

# Restart unhealthy dependency
docker compose restart <dependency>

# Wait for service to recover
docker compose logs <service_name> -f
```

### Cause 5: Code Regression

**Symptoms:**
- Queue lag started after recent deployment
- Error logs show new exception types
- Processing latency increased significantly

**Fix:**
```bash
# Check recent deployments
git log --oneline -10

# Rollback if regression confirmed
git revert <commit>
docker compose up -d --build <service_name>

# Monitor for improvement
```

---

## Resolution Steps

### Immediate (Stop the Bleeding)

1. **Scale the service** (if CPU/memory available):
   ```bash
   docker compose up -d --scale <service_name>=3
   ```

2. **Verify processing resumes**:
   ```bash
   # Watch queue depth decrease
   watch -n 5 'curl -u guest:guest http://localhost:15672/api/queues/<queue> | jq ".messages_ready"'
   ```

3. **Monitor error rate**:
   ```bash
   # Check failed queue
   curl -u guest:guest http://localhost:15672/api/queues/<queue>.failed | jq ".messages_ready"
   ```

### Short-Term (Stabilize)

1. **Identify bottleneck**:
   - Check service logs for slow operations
   - Review resource usage (CPU/memory/disk)
   - Profile slow code paths if needed

2. **Optimize if possible**:
   - Increase batch size (if applicable)
   - Add indexes to database queries
   - Cache frequently accessed data

3. **Add monitoring**:
   - Create dashboard panel for this queue
   - Set up Slack notification for future alerts

### Long-Term (Prevent Recurrence)

1. **Capacity planning**:
   - Calculate sustained throughput requirements
   - Right-size service replicas for peak load
   - Add autoscaling if available

2. **Code optimization**:
   - Profile and optimize hot paths
   - Reduce database round-trips
   - Use connection pooling

3. **Architecture changes** (if needed):
   - Split large messages into smaller units
   - Implement backpressure/throttling
   - Add caching layer

---

## Verification

After resolution, verify:

```bash
# 1. Queue depth is decreasing
curl -u guest:guest http://localhost:15672/api/queues/<queue> | jq ".messages_ready"

# 2. Processing throughput is acceptable
docker compose exec monitoring promtool query instant 'rate(copilot_<service>_messages_processed_total[5m])'

# 3. Error rate is low
docker compose exec monitoring promtool query instant 'rate(copilot_<service>_failures_total[5m])'

# 4. Latency is within SLO
docker compose exec monitoring promtool query instant 'histogram_quantile(0.95, rate(copilot_<service>_processing_duration_seconds_bucket[5m]))'
```

**Success Criteria:**
- ✅ Queue depth < 100 messages
- ✅ Message age < 5 minutes
- ✅ Error rate < 1%
- ✅ P95 latency within SLO target

---

## Escalation

### When to Escalate

- Queue lag not resolved after 30 minutes
- Error rate remains > 5%
- Dependency failures (MongoDB/RabbitMQ down)
- Resource exhaustion (CPU/memory/disk full)
- Unknown root cause

### Who to Contact

1. **Team Lead** - For architectural decisions
2. **DevOps Engineer** - For infrastructure scaling
3. **On-Call Engineer** - After hours (PagerDuty)

### Incident Severity

- **P3 (Warning)**: Queue depth high but draining
- **P2 (Error)**: Queue depth critical or sustained high lag
- **P1 (Critical)**: Service down, data loss risk, SLO breach

---

## Related

- **Dashboards**: [Queue Status](http://localhost:8080/grafana/d/queue-status)
- **Alerts**: `ParsingQueueDepthHigh`, `QueueMessageAgeHigh`
- **Docs**: [SERVICE_MONITORING.md](../SERVICE_MONITORING.md)
- **Architecture**: [QUEUE_ARCHITECTURE.md](../QUEUE_ARCHITECTURE.md)

---

## Post-Incident

After resolving:

1. **Document incident** in incident log
2. **Update runbook** with new learnings
3. **Create follow-up tasks** for improvements
4. **Schedule postmortem** if P1/P2 incident
5. **Update capacity planning** if scaling was needed
