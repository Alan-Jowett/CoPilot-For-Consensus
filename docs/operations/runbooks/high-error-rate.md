<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Runbook: High Error Rate

## Alert Details

**Alert Names:**
- `ParsingErrorRateHigh` / `ParsingErrorRateCritical`
- `ChunkingErrorRateHigh`
- `EmbeddingErrorRateHigh`
- `SummarizationErrorRateHigh`
- `IngestionAPIErrorRateHigh`
- `ReportingAPIErrorRateHigh`

**Severity:** Warning → Critical  
**Component:** Service Processing

---

## Symptoms

- Error rate exceeds 1% (SLO threshold)
- Failed queue accumulating messages
- High failure metrics in Prometheus
- Error logs showing repeated exceptions

**User Impact:**
- Processing failures
- Incomplete data in reports
- Failed API requests
- Degraded system reliability

---

## Diagnosis

### 1. Check Error Rate

In Prometheus (http://localhost:9090):

```promql
# Current error rate (%)
(rate(copilot_<service>_failures_total[5m]) / rate(copilot_<service>_messages_processed_total[5m])) * 100

# Error count by type
sum by (error_type) (rate(copilot_<service>_failures_total[5m]))
```

### 2. Identify Error Types

```bash
# Check service logs
docker compose logs <service_name> --tail=200 | grep -i error

# Group errors by type
docker compose logs <service_name> --since 30m | grep ERROR | cut -d: -f3 | sort | uniq -c | sort -rn
```

### 3. Check Failed Queue

```bash
# Check failed queue depth
curl -u guest:guest http://localhost:15672/api/queues/<service>.failed | jq ".messages_ready"

# Inspect failed messages
docker compose run --rm <service_name> python scripts/manage_failed_queues.py inspect <service>.failed --limit 10
```

### 4. Check Dependencies

```bash
# MongoDB connectivity
docker compose exec <service_name> python -c "from pymongo import MongoClient; MongoClient('mongodb://documentdb:27017').admin.command('ping')"

# RabbitMQ connectivity
docker compose exec <service_name> python -c "import pika; conn = pika.BlockingConnection(pika.ConnectionParameters('messagebus')); print('OK')"

# Qdrant connectivity (for embedding service)
curl http://localhost:6333/collections
```

---

## Common Error Patterns

### Pattern 1: Connection Errors

**Symptoms:**
- `ConnectionError`, `TimeoutError` in logs
- Errors grouped by connection-related types
- Dependency service unhealthy

**Root Causes:**
- Network issues between containers
- Dependency service down or overloaded
- Connection pool exhausted
- DNS resolution failure

**Fix:**
```bash
# 1. Check dependency health
docker compose ps

# 2. Restart unhealthy services
docker compose restart <dependency>

# 3. Check network
docker network inspect <project>_default

# 4. Verify DNS resolution
docker compose exec <service_name> ping documentdb

# 5. Check connection pool settings
# Review service configuration for max connections
```

### Pattern 2: Data Validation Errors

**Symptoms:**
- `ValidationError`, `SchemaError` in logs
- Errors on specific message types
- Failed messages have malformed data

**Root Causes:**
- Schema changes not backward compatible
- Upstream service sending invalid data
- Missing required fields

**Fix:**
```bash
# 1. Inspect failed messages
docker compose run --rm <service_name> python scripts/manage_failed_queues.py inspect <service>.failed --limit 5

# 2. Identify schema violations
# Review message structure vs. expected schema

# 3. Fix upstream service if sending bad data
# Or update schema validator to be more lenient

# 4. Reprocess after fix
docker compose run --rm <service_name> python scripts/manage_failed_queues.py requeue <service>.failed --limit 100
```

### Pattern 3: Resource Exhaustion

**Symptoms:**
- `MemoryError`, `Timeout` in logs
- Errors increase with system load
- OOM kills in system logs

**Root Causes:**
- Insufficient memory/CPU allocated
- Memory leaks
- Large message payloads
- Inefficient algorithms

**Fix:**
```bash
# 1. Check resource usage
docker stats <service_name>

# 2. Increase resource limits (docker-compose.yml)
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G

# 3. Restart with new limits
docker compose up -d <service_name>

# 4. If memory leak, investigate code
# Review memory profiling tools (memory_profiler, tracemalloc)
```

### Pattern 4: Code Bugs

**Symptoms:**
- Specific exception types dominating errors
- Errors started after recent deployment
- Stack traces point to new code

**Root Causes:**
- Regression in recent code change
- Unhandled edge cases
- Incorrect assumptions about data

**Fix:**
```bash
# 1. Identify when errors started
# Check deployment timeline vs. error spike

# 2. Review recent commits
git log --oneline --since="1 day ago"
git diff <previous_working_commit> <current_commit>

# 3. Rollback if regression confirmed
git revert <problematic_commit>
docker compose up -d --build <service_name>

# 4. Verify error rate drops
watch -n 10 'curl -s http://localhost:9090/api/v1/query?query=rate(copilot_<service>_failures_total[5m])'
```

### Pattern 5: External API Failures

**Symptoms:**
- Errors from external API calls (Ollama, Azure OpenAI)
- Rate limit errors
- Authentication failures

**Root Causes:**
- API rate limiting
- Invalid/expired credentials
- API service outage
- Network connectivity

**Fix:**
```bash
# For Ollama issues:
docker compose ps ollama
docker compose logs ollama --tail=100
curl http://localhost:11434/api/tags

# For Azure OpenAI:
# Check credentials in environment
docker compose exec <service_name> env | grep AZURE

# Check rate limits
# Review Azure portal for quota/throttling

# Implement retry with backoff
# Update service code to handle transient failures gracefully
```

---

## Resolution Steps

### Immediate (Stop Error Growth)

1. **Identify dominant error type**:
   ```bash
   docker compose logs <service_name> --since 30m | grep ERROR | grep -oP "(?<=exception: )\w+" | sort | uniq -c | sort -rn | head -5
   ```

2. **Check if errors are transient**:
   ```bash
   # Watch error rate
   watch -n 10 'docker compose exec monitoring promtool query instant "rate(copilot_<service>_failures_total[5m])"'
   ```

3. **Pause processing if critical**:
   ```bash
   # Scale down to stop new errors
   docker compose stop <service_name>
   ```

### Short-Term (Fix Root Cause)

1. **Fix identified issue** (see patterns above)

2. **Restart service** with fix:
   ```bash
   docker compose up -d <service_name>
   ```

3. **Monitor error rate**:
   ```bash
   # Should decrease to < 1%
   docker compose exec monitoring promtool query instant '(rate(copilot_<service>_failures_total[5m]) / rate(copilot_<service>_messages_processed_total[5m])) * 100'
   ```

4. **Reprocess failed messages** (after confirming fix):
   ```bash
   docker compose run --rm <service_name> python scripts/manage_failed_queues.py requeue <service>.failed --limit 1000
   ```

### Long-Term (Prevent Recurrence)

1. **Add error handling**:
   - Retry transient failures with exponential backoff
   - Graceful degradation for external API failures
   - Circuit breaker for failing dependencies

2. **Improve validation**:
   - Validate messages earlier in pipeline
   - Add schema versioning
   - Provide better error messages

3. **Add monitoring**:
   - Alert on specific error types
   - Track error rate per error type
   - Dashboard for error trends

4. **Testing**:
   - Add tests for edge cases that caused errors
   - Integration tests for dependency failures
   - Load testing to catch resource issues

---

## Verification

After resolution:

```bash
# 1. Error rate below threshold
docker compose exec monitoring promtool query instant '(rate(copilot_<service>_failures_total[5m]) / rate(copilot_<service>_messages_processed_total[5m])) * 100'
# Expected: < 1%

# 2. Failed queue not growing
watch -n 10 'curl -u guest:guest http://localhost:15672/api/queues/<service>.failed | jq ".messages_ready"'

# 3. Processing throughput normal
docker compose exec monitoring promtool query instant 'rate(copilot_<service>_messages_processed_total{status="success"}[5m])'

# 4. No errors in recent logs
docker compose logs <service_name> --since 10m | grep -i error
# Expected: No errors or < 1% of logs
```

**Success Criteria:**
- ✅ Error rate < 1% for 15 minutes
- ✅ Failed queue depth stable or decreasing
- ✅ No recurring error patterns in logs
- ✅ Processing throughput restored

---

## Escalation

### When to Escalate

- Error rate > 5% for 30 minutes
- Cannot identify root cause
- Fix requires architecture changes
- External dependency failure (vendor)
- Data corruption suspected

### Who to Contact

1. **Service Owner** - For code issues
2. **Database Team** - For MongoDB errors
3. **DevOps** - For infrastructure issues
4. **Vendor Support** - For third-party API issues
5. **On-Call** - After hours (PagerDuty)

### Incident Severity

- **P3 (Warning)**: 1-5% error rate, no user impact
- **P2 (Error)**: 5-10% error rate, degraded service
- **P1 (Critical)**: > 10% error rate, service unusable

---

## Related

- **Dashboards**: [Service Metrics](http://localhost:8080/grafana/d/service-metrics)
- **Alerts**: See `infra/prometheus/alerts/slo_errors.yml`
- **Docs**: [FAILED_QUEUE_OPERATIONS.md](../../../documents/FAILED_QUEUE_OPERATIONS.md)
- **Runbooks**: [service-down.md](./service-down.md), [high-queue-lag.md](./high-queue-lag.md)

---

## Post-Incident

1. **Analyze root cause** thoroughly
2. **Document in incident log** with timeline
3. **Create follow-up tasks**:
   - Code fixes
   - Test improvements
   - Monitoring enhancements
4. **Update runbook** with new learnings
5. **Schedule postmortem** if P1/P2
6. **Share learnings** with team
