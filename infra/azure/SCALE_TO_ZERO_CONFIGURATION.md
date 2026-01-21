<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Container Apps Scale-to-Zero Configuration

This document describes the scale-to-zero configuration implemented for all Container Apps services to optimize costs by eliminating idle compute charges.

## Overview

All services in the Container Apps environment are configured to scale to zero when idle:

- **HTTP-triggered services** scale based on incoming HTTP request concurrency
- **Service Bus message consumers** scale based on queue/subscription depth via KEDA

This achieves significant cost savings (estimated 35-50% reduction) while maintaining responsiveness to workload demands.

## Architecture

### HTTP Services (Scale on HTTP Traffic)

The following services scale based on HTTP concurrent requests:

| Service | Port | Ingress | Scale Trigger |
|---------|------|---------|---------------|
| **gateway** | 8080 | External | HTTP concurrent requests (10 per replica) |
| **ui** | 80 | Internal | HTTP concurrent requests (10 per replica) |
| **reporting** | 8080 | Internal | HTTP concurrent requests (10 per replica) |
| **ingestion** | 8001 | Internal | HTTP concurrent requests (10 per replica) |
| **auth** | 8090 | Internal | HTTP concurrent requests (10 per replica) |
| **qdrant** | 6333 | Internal | HTTP concurrent requests (10 per replica) |

### Service Bus Message Consumers (Scale on Queue Depth)

The following services scale based on Azure Service Bus message queue depth using KEDA:

| Service | Topic | Subscription | Messages per Replica | Activation Threshold |
|---------|-------|--------------|---------------------|---------------------|
| **parsing** | copilot.events | parsing | 5 | 1 |
| **chunking** | copilot.events | chunking | 5 | 1 |
| **embedding** | copilot.events | embedding | 5 | 1 |
| **orchestrator** | copilot.events | orchestrator | 5 | 1 |
| **summarization** | copilot.events | summarization | 5 | 1 |

## Configuration Details

### Scale Configuration

All services are configured with:

```bicep
scale: {
  minReplicas: 0  // Scale to zero when idle
  maxReplicas: 2-3  // Cap based on service (gateway=3, others=2)
  rules: [...]  // HTTP or Service Bus scaling rules
}
```

### HTTP Scaling Rules

HTTP services use the built-in HTTP scaler:

```bicep
rules: [
  {
    name: 'http-scaling'
    http: {
      metadata: {
        concurrentRequests: '10'  // Scale up when >10 concurrent requests
      }
    }
  }
]
```

### Service Bus Scaling Rules (KEDA)

Message consumer services use the KEDA Azure Service Bus scaler:

```bicep
rules: [
  {
    name: 'servicebus-scaling'
    custom: {
      type: 'azure-servicebus'
      metadata: {
        topicName: 'copilot.events'
        subscriptionName: '<service-name>'
        messageCount: '5'  // Target: 5 messages per replica
        activationMessageCount: '1'  // Wake from 0 when >=1 message
        namespace: '<servicebus-namespace>.servicebus.windows.net'
      }
    }
  }
]
```

**Authentication**: 

KEDA scalers use the container app's user-assigned managed identity automatically. Azure Container Apps automatically configures KEDA to authenticate with Azure Service Bus using the app's managed identity when:
1. The container app has a user-assigned managed identity configured
2. The managed identity has the required RBAC roles (Azure Service Bus Data Receiver)
3. No explicit auth configuration is provided in the scale rule

This is the **recommended approach** for Container Apps as it:
- Eliminates the need for connection strings or secrets
- Leverages existing RBAC role assignments
- Simplifies configuration and maintenance

## Behavior

### Cold Start Behavior

When a service is scaled to zero:

1. **First request/message after idle**:
   - Container Apps detects the trigger (HTTP request or Service Bus message)
   - Platform starts a new container instance
   - Cold start delay: typically 5-15 seconds
   - Request/message is queued until the instance is ready

2. **Subsequent requests/messages**:
   - Processed immediately by the running instance
   - No cold start delay

### Scaling Up

- **HTTP services**: Scale up when concurrent request count exceeds threshold (10)
- **Service Bus consumers**: Scale up when message count exceeds threshold (5 messages per replica)
- New replicas are added incrementally up to `maxReplicas`

### Scaling Down

- **HTTP services**: Scale down when concurrent requests drop
- **Service Bus consumers**: Scale down when message queue depth decreases
- Cooldown period prevents rapid scaling oscillation
- Eventually scales to 0 when completely idle

## Operational Considerations

### Cold Start Impact

**Acceptable for**:
- Dev/test environments (low traffic)
- Batch workloads with tolerance for initial latency
- Event-driven processing with asynchronous workflows

**Mitigation strategies** (if cold starts become problematic):
- Set `minReplicas: 1` for critical services in production
- Use Azure Container Apps Premium plan for faster cold starts
- Pre-warm services during known high-traffic periods

### Qdrant Vector Database Considerations

**⚠️ IMPORTANT: Data Persistence**

The Qdrant vector database service is currently configured **without persistent storage**, suitable for development/ephemeral use. When Qdrant scales to zero and restarts:

- **All vector embeddings stored in memory will be lost**
- **Re-ingestion of all data will be required** to rebuild the vector index
- Embedding services depend on Qdrant having persistent data

**Recommendations**:

1. **For Development/Test**: 
   - Accept data loss and re-ingest after cold starts
   - Set `minReplicas: 1` for Qdrant if frequent re-ingestion is disruptive

2. **For Production**:
   - Add persistent storage (Azure Files volume mount) before enabling scale-to-zero
   - See: [Azure Container Apps Storage Mounts](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts)
   - OR set `minReplicas: 1` for Qdrant to maintain data availability

3. **Alternative**: Use Azure AI Search as the vector store backend (configured via `vectorStoreBackend` parameter) which has built-in persistence

### Monitoring Implications

**Prometheus/Grafana Scraping**:
- Services at 0 replicas will not expose metrics endpoints
- Metrics timeseries will have gaps during idle periods
- Consider push-based metrics (Pushgateway) or Application Insights for continuous monitoring

**Recommendations**:
- Monitor scale events via Container Apps logs
- Track cold start latency via Application Insights
- Alert on excessive scaling activity (may indicate configuration issues)

### Message Processing

**Service Bus Consumer Notes**:
- Messages are not lost when services scale to 0
- Service Bus queues retain messages until processed
- KEDA monitors queue depth and triggers scale-up
- Dead-letter queues handle persistent failures (10 retries configured)

**Idempotency**:
- All message handlers should be idempotent
- Duplicate processing may occur during scale transitions
- Use message deduplication in Service Bus if needed

## Cost Savings Analysis

### Assumptions
- **Message volume**: 1000 messages/day (30K/month)
- **HTTP traffic**: Low (dev/test environment with intermittent access)
- **Idle time**: ~16 hours/day (nighttime, weekends)

### Cost Comparison

| Configuration | Compute Cost | Notes |
|--------------|--------------|-------|
| **Always-on (minReplicas=1)** | ~$200-400/month | 24/7 running containers for up to 10 services |
| **Scale-to-zero (minReplicas=0)** | ~$130-260/month | Pay only for active time + execution |
| **Annual savings** | ~$840-1,680/year | 35-45% reduction |

**Note**: Cost estimates vary based on the number of services deployed (5-10) and actual usage patterns. See README.md for detailed breakdown of all infrastructure costs.

**Savings increase with**:
- More services
- Longer idle periods
- Lower message/request volume

## Tuning Parameters

### Adjustable Settings

**HTTP Services**:
- `concurrentRequests`: Increase for higher capacity per replica (trade-off: slower scale-up)
- `maxReplicas`: Cap based on workload expectations and cost constraints

**Service Bus Consumers**:
- `messageCount`: Messages per replica (5 = process 5 messages per instance)
- `activationMessageCount`: Threshold to wake from 0 (set to 1 for immediate activation)
- `maxReplicas`: Cap based on Service Bus throughput limits

**Example tuning scenarios**:

1. **High-throughput production**:
   ```bicep
   minReplicas: 1  // Avoid cold starts
   maxReplicas: 10
   messageCount: '10'  // More messages per replica
   ```

2. **Cost-optimized dev/test**:
   ```bicep
   minReplicas: 0  // Current configuration
   maxReplicas: 2
   messageCount: '5'
   ```

3. **Bursty workloads**:
   ```bicep
   minReplicas: 0
   maxReplicas: 5  // Higher max for burst capacity
   activationMessageCount: '10'  // Avoid waking for tiny queues
   ```

## Validation

### Verify Scale-to-Zero

1. **Check initial state**:
   ```bash
   az containerapp show --name <app-name> --resource-group <rg> --query "properties.template.scale"
   ```

2. **Monitor replica count**:
   ```bash
   az containerapp replica list --name <app-name> --resource-group <rg>
   ```

3. **Trigger scale-up**:
   - HTTP services: Send HTTP requests
   - Message consumers: Publish messages to Service Bus topic

4. **Verify scale-down**:
   - Wait for idle period (typically 5-10 minutes)
   - Confirm replicas drop to 0

### Test Cold Start Latency

1. Ensure service is at 0 replicas (idle for >10 minutes)
2. Send first request/message
3. Measure time to first response (expected: 5-15 seconds)
4. Send subsequent requests (expected: milliseconds)

## Troubleshooting

### Service Not Scaling Up

**Symptoms**: Requests/messages timing out, service stays at 0 replicas

**Possible causes**:
1. KEDA scaler misconfiguration (check namespace, topic, subscription names)
2. Managed identity lacks Service Bus permissions
3. Container image startup failure

**Resolution**:
- Check Container Apps logs: `az containerapp logs show`
- Verify Service Bus RBAC roles assigned to managed identity
- Test container startup manually

### Excessive Scaling Activity

**Symptoms**: Constant scale up/down, high costs despite scale-to-zero

**Possible causes**:
1. Threshold too sensitive (low `messageCount` or `concurrentRequests`)
2. Short cooldown period
3. Background health checks triggering HTTP requests

**Resolution**:
- Increase `messageCount` or `concurrentRequests`
- Adjust scale-down settings (platform-managed, but influenced by thresholds)
- Review logs for unexpected traffic patterns

### Message Processing Delays

**Symptoms**: Messages queued but service not scaling

**Possible causes**:
1. Service Bus namespace unreachable from Container Apps environment
2. KEDA unable to authenticate
3. `activationMessageCount` threshold not met

**Resolution**:
- Verify Service Bus network connectivity (VNet integration, firewall rules)
- Confirm managed identity has "Azure Service Bus Data Receiver" role
- Check KEDA operator logs in Container Apps environment (requires support ticket)

## References

- [Azure Container Apps Scaling](https://learn.microsoft.com/azure/container-apps/scale-app)
- [KEDA Azure Service Bus Scaler](https://keda.sh/docs/scalers/azure-service-bus/)
- [Container Apps HTTP Scaling](https://learn.microsoft.com/azure/container-apps/scale-app#http)
- [Container Apps KEDA Scalers](https://learn.microsoft.com/azure/container-apps/scale-app#keda-scalers)
- [Azure Container Apps Pricing](https://azure.microsoft.com/pricing/details/container-apps/)
