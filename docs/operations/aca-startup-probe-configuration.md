# ACA Startup Probe and Memory Configuration

## Overview

This document describes the startup probe, readiness probe, and memory configurations added to Azure Container Apps services to resolve exit 137 restarts and probe failures.

## Problem Statement

Services were experiencing:
- Frequent StartUp probe failures (311 for chunking, 274 for summarization, 246 for orchestrator)
- Container terminations with exit code 137 (SIGKILL/OOM) - 120+ occurrences
- Service Bus subscription backlogs not draining due to crashlooping services

**Root Causes:**
1. No explicit startup/readiness probes configured in Bicep (ACA relied on defaults)
2. Memory limit of 0.5Gi (512MB) too low for startup dependencies and runtime operations
3. Cold start time not accounted for (Cosmos, Service Bus, KeyVault, model loading)

## Solution

### 1. Startup Probes

**Purpose:** Allow sufficient time for services to initialize dependencies before marking as failed.

| Service | Path | Initial Delay | Period | Timeout | Failure Threshold | Max Wait Time |
|---------|------|---------------|--------|---------|-------------------|---------------|
| chunking | /health | 10s | 5s | 3s | 12 | 60s |
| embedding | /health | 30s | 5s | 3s | 24 | 120s |
| orchestrator | /health | 10s | 5s | 3s | 12 | 60s |
| summarization | /health | 30s | 5s | 3s | 24 | 120s |
| auth | /health | 5s | 5s | 3s | 12 | 60s |

**Rationale:**
- **Embedding/Summarization** get longer startup times (120s) due to model loading
- **Chunking/Orchestrator** get moderate startup times (60s) for Cosmos/Service Bus connections
- **Auth** gets shortest startup time (60s) as it's lightweight with minimal dependencies

### 2. Readiness Probes

**Purpose:** Indicate when service is ready to accept traffic (subscriber threads running).

| Service | Path | Initial Delay | Period | Timeout | Failure Threshold |
|---------|------|---------------|--------|---------|-------------------|
| chunking | /readyz | 5s | 10s | 3s | 3 |
| embedding | /readyz | 5s | 10s | 3s | 3 |
| orchestrator | /readyz | 5s | 10s | 3s | 3 |
| summarization | /readyz | 5s | 10s | 3s | 3 |
| auth | /readyz | 3s | 10s | 3s | 3 |

**Health Check Logic:**
- `/health` - Always returns 200 with service stats (used for startup probe)
- `/readyz` - Returns 200 only when service is fully initialized and subscriber thread is running

### 3. Memory Increases

| Service | Old Memory | New Memory | Rationale |
|---------|------------|------------|-----------|
| chunking | 0.5Gi | 1Gi | Processing large email bodies, document chunking |
| embedding | 0.5Gi | **2Gi** | Loading embedding models (Sentence Transformers) |
| orchestrator | 0.5Gi | 1Gi | Managing workflow state, LLM calls |
| summarization | 0.5Gi | **2Gi** | LLM operations, vector search, context building |
| auth | 0.5Gi | 0.5Gi | Lightweight service, kept at 512MB |

### 4. Startup Diagnostics

All services now log:
- Memory usage at key startup stages (using `psutil` when available)
- Timing for each dependency connection:
  - Config load time
  - Publisher connect time
  - Subscriber connect time
  - Document store connect time
  - Vector store connect time (embedding/summarization)
- Total startup time

**Example Log Output:**
```
INFO: Starting Chunking Service (version 1.0.0)
INFO: [Startup Diagnostics] Initial startup: Memory usage = 45.23 MB
INFO: Configuration loaded successfully in 0.12s
INFO: [Startup Diagnostics] After config load: Memory usage = 52.34 MB
INFO: Publisher connected to message bus in 1.45s
INFO: [Startup Diagnostics] After publisher connect: Memory usage = 68.91 MB
INFO: Subscriber connected to message bus in 0.89s
INFO: [Startup Diagnostics] After subscriber connect: Memory usage = 75.12 MB
INFO: Document store connected successfully in 2.34s
INFO: [Startup Diagnostics] After document store connect: Memory usage = 112.45 MB
INFO: [Startup Diagnostics] Service fully initialized in 5.23s
INFO: [Startup Diagnostics] Service ready: Memory usage = 115.67 MB
```

## Implementation Files

### Bicep Changes
- `infra/azure/modules/containerapps.bicep` - Added probes and increased memory limits

### Service Changes (added /readyz endpoint)
- `chunking/main.py` - Added readyz endpoint and startup diagnostics
- `embedding/main.py` - Added readyz endpoint and startup diagnostics
- `orchestrator/main.py` - Added readyz endpoint and startup diagnostics
- `summarization/main.py` - Added readyz endpoint and startup diagnostics
- `auth/main.py` - Already had /readyz endpoint (no changes)

## Testing

### Local Testing
```bash
# Start a service locally with noop config
cd chunking
python main.py

# In another terminal, check endpoints
curl http://localhost:8000/health
curl http://localhost:8000/readyz
```

### Azure Deployment
After deploying to Azure Container Apps:
1. Monitor Container App system logs for probe failures
2. Check service logs for startup diagnostic messages
3. Verify memory usage stays below new limits
4. Monitor for exit code 137 (should be eliminated)

### Expected Outcomes
- ✅ Zero StartUp probe failures after initial deployment
- ✅ Readiness probes correctly reflect subscriber thread status
- ✅ No exit code 137 terminations (OOM kills)
- ✅ Service Bus subscriptions drain consistently
- ✅ Stable KEDA scaling without flapping

## Monitoring

### Key Metrics to Track
- **Container restarts** - should drop to zero for normal operations
- **Probe failures** - StartUp and Readiness probe failures should be eliminated
- **Memory usage** - should stay comfortably below new limits (75-85% utilization)
- **Startup time** - logged in service diagnostics, should be < 60s for most services
- **Service Bus message backlog** - should drain consistently

### Alerts to Configure
1. Container restart count > 0 in 5 minutes
2. Probe failure rate > 1% over 10 minutes
3. Memory usage > 90% of limit for 5 minutes
4. Service Bus message age > 5 minutes

## Rollback Plan

If issues occur after deployment:

1. **Immediate rollback**: Revert to previous ACA revision via Azure Portal
2. **Memory issues**: Increase memory further (try 1.5Gi → 2Gi, or 2Gi → 3Gi)
3. **Probe issues**: Increase startup probe timeout (failureThreshold or initialDelaySeconds)
4. **Code issues**: Revert service main.py changes

## Future Improvements

1. **Dynamic probe configuration** - Adjust probe settings based on environment (dev/staging/prod)
2. **Adaptive memory scaling** - Use ACA autoscaling with memory metrics
3. **Enhanced diagnostics** - Add structured logs for Azure Monitor queries
4. **Circuit breakers** - Implement circuit breakers for dependency failures
5. **Graceful degradation** - Allow services to start with partial dependencies

## Related Issues

- #1006 - embedding ChunksPrepared schema validation failures
- #1008 - parsing Cosmos 409 conflicts
- #1005 - orchestrator missing chunk_ids data inconsistency
- #1007 - chunking Cosmos conflicts
- #1011 - reporting azure-servicebus handler crash

## References

- [Azure Container Apps Probes Documentation](https://learn.microsoft.com/azure/container-apps/health-probes)
- [Kubernetes Probes Best Practices](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [OOM Kill Debugging](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/#my-pod-stays-waiting)
