# Azure Functions vs Container Apps: Side-by-Side Comparison

This document provides a technical comparison of the Container App and Azure Function implementations for message consumer services.

## Chunking Service Comparison

### File Structure

**Container App (`chunking/`)**:
```
chunking/
├── main.py (230 lines)
├── app/
│   ├── __init__.py
│   └── service.py (572 lines)
├── Dockerfile
├── requirements.txt
└── tests/
```

**Azure Function (`functions/chunking_function/`)**:
```
chunking_function/
├── __init__.py (200 lines)
├── function.json (binding config)
├── host.json (runtime config)
├── requirements.txt
└── (reuses ../chunking/app/service.py)
```

### Code Comparison

#### Container App: main.py (Excerpt)

```python
# FastAPI app setup
app = FastAPI(title="Chunking Service", version=__version__)

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy", ...}

@app.get("/stats")
def get_stats():
    """Get chunking statistics."""
    return chunking_service.get_stats()

def start_subscriber_thread(service):
    """Start event subscriber in separate thread."""
    try:
        service.start()
        service.subscriber.start_consuming()  # Blocking
    except Exception as e:
        logger.error(f"Subscriber error: {e}")
        raise

def main():
    # Create subscriber
    subscriber = create_subscriber(
        message_bus_type=config.message_bus_type,
        host=config.message_bus_host,
        queue_name="json.parsed",
    )
    subscriber.connect()
    
    # Create service
    chunking_service = ChunkingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=subscriber,
        chunker=chunker,
    )
    
    # Start subscriber thread
    subscriber_thread = threading.Thread(
        target=start_subscriber_thread,
        args=(chunking_service,),
        daemon=False,
    )
    subscriber_thread.start()
    
    # Start HTTP server
    uvicorn.run(app, host="0.0.0.0", port=config.http_port)
```

#### Azure Function: __init__.py (Excerpt)

```python
# No FastAPI - function is entry point
# No health endpoint - handled by platform

_chunking_service: ChunkingService | None = None

def get_chunking_service() -> ChunkingService:
    """Lazy initialization - reused across invocations."""
    global _chunking_service
    if _chunking_service is not None:
        return _chunking_service
    
    # Initialize once (same code as Container App)
    config = load_typed_config("chunking")
    publisher = create_publisher(...)
    document_store = create_document_store(...)
    chunker = create_chunker(...)
    
    _chunking_service = ChunkingService(
        document_store=document_store,
        publisher=publisher,
        subscriber=None,  # Not needed
        chunker=chunker,
    )
    return _chunking_service

def main(msg: func.ServiceBusMessage) -> None:
    """Function entry point - triggered by Service Bus."""
    service = get_chunking_service()
    event_data = json.loads(msg.get_body().decode('utf-8'))
    service.process_messages(event_data.get("data", {}))
```

### Configuration Comparison

#### Container App: Service Bus Consumer

```python
# Manual subscriber configuration
subscriber = create_subscriber(
    message_bus_type="azureservicebus",
    host=f"{namespace}.servicebus.windows.net",
    queue_name="json.parsed",
    **get_azure_servicebus_kwargs(),
)
subscriber.connect()
subscriber.subscribe(
    event_type="JSONParsed",
    exchange="copilot.events",
    routing_key="json.parsed",
    callback=self._handle_json_parsed,
)
subscriber.start_consuming()  # Blocking
```

#### Azure Function: Service Bus Trigger

```json
{
  "bindings": [
    {
      "name": "msg",
      "type": "serviceBusTrigger",
      "direction": "in",
      "queueName": "json.parsed",
      "connection": "AzureWebJobsServiceBus"
    }
  ]
}
```

**Key Difference**: Azure Functions runtime handles all message consumption automatically.

### Deployment Comparison

#### Container App Deployment

```bash
# 1. Build Docker image
docker build -t chunking:latest .

# 2. Push to Azure Container Registry
az acr login --name myregistry
docker tag chunking:latest myregistry.azurecr.io/chunking:latest
docker push myregistry.azurecr.io/chunking:latest

# 3. Deploy to Container Apps
az containerapp update \
  --name chunking \
  --resource-group mygroup \
  --image myregistry.azurecr.io/chunking:latest
```

**Time**: ~5-10 minutes (build + push + deploy)

#### Azure Function Deployment

```bash
# Direct code deployment (no Docker)
func azure functionapp publish copilot-func-dev
```

**Time**: ~1-2 minutes

### Scaling Comparison

#### Container App Scaling

```bicep
scale: {
  minReplicas: 1  // Always-on
  maxReplicas: 10
  rules: [
    {
      name: "queue-depth"
      custom: {
        type: "azure-servicebus"
        metadata: {
          queueName: "json.parsed"
          messageCount: "100"  // Scale at 100 messages
        }
      }
    }
  ]
}
```

**Behavior**:
- 1 replica always running (even if queue is empty)
- Scales up when queue depth > 100 messages
- Manual configuration required

#### Azure Function Scaling

```json
{
  "extensions": {
    "serviceBus": {
      "prefetchCount": 100,
      "messageHandlerOptions": {
        "maxConcurrentCalls": 32
      }
    }
  }
}
```

**Behavior**:
- 0 instances when queue is empty (true scale-to-zero)
- Automatically scales based on queue depth
- Runtime handles scaling decisions

### Monitoring Comparison

#### Container App Monitoring

**Prometheus Metrics**:
```python
metrics_collector.increment("chunking_messages_processed_total")
metrics_collector.observe("chunking_duration_seconds", duration)
```

**Scraping**: Prometheus scrapes `/metrics` endpoint every 15 seconds

**Dashboard**: Grafana queries Prometheus

#### Azure Function Monitoring

**Application Insights (Automatic)**:
- Invocation count
- Success/failure rate
- Execution duration
- Exception tracking
- Dependency calls (Cosmos DB, Service Bus)

**Custom Metrics** (Optional):
```python
# Can still use Prometheus if desired
metrics_collector.increment("chunking_messages_processed_total")
metrics_collector.safe_push()  # Push to Pushgateway
```

### Cost Comparison (1,000 messages/day)

| Aspect | Container App | Azure Function |
|--------|--------------|----------------|
| **Always-On Cost** | $29.30/month | $0 (scale-to-zero) |
| **Execution Cost** | Included | $0.20/month |
| **Storage** | N/A | $5/month (shared) |
| **Total** | **$29.30/month** | **$5.20/month** |
| **Savings** | - | **82%** |

### Performance Comparison

| Metric | Container App | Function (Cold) | Function (Warm) |
|--------|--------------|-----------------|-----------------|
| **Startup** | N/A (always on) | ~3 seconds | N/A |
| **Processing** | ~2 seconds | ~2 seconds | ~2 seconds |
| **End-to-End** | ~2 seconds | ~5 seconds | ~2 seconds |

### Error Handling Comparison

#### Container App

```python
def _handle_json_parsed(self, event: dict[str, Any]):
    try:
        self.process_messages(event.get("data", {}))
    except Exception as e:
        logger.error(f"Error: {e}")
        raise  # Message will be retried by subscriber
```

**Retry Behavior**: Configured in subscriber (e.g., 5 retries with exponential backoff)

#### Azure Function

```python
def main(msg: func.ServiceBusMessage) -> None:
    try:
        service.process_messages(event_data)
    except Exception as e:
        logger.error(f"Error: {e}")
        raise  # Azure Functions runtime handles retry
```

**Retry Behavior**: Configured in function.json:
```json
{
  "retry": {
    "strategy": "exponentialBackoff",
    "maxRetryCount": 5,
    "minimumInterval": "00:00:05",
    "maximumInterval": "00:05:00"
  }
}
```

**Advantages**:
- Automatic dead-letter queue routing after max retries
- Built-in poison message handling
- Per-function retry configuration

## Summary

### Container Apps Advantages

✅ Consistent with other services in the architecture  
✅ Full control over runtime and dependencies  
✅ Existing Prometheus/Grafana monitoring stack  
✅ No cold start latency  
✅ Better for high-volume production workloads (>200K msgs/month)

### Azure Functions Advantages

✅ **82% cost savings** for low-volume workloads  
✅ True scale-to-zero (no idle cost)  
✅ Native Service Bus integration (less code)  
✅ Automatic scaling based on queue depth  
✅ Simpler deployment (no Docker)  
✅ Built-in retry and dead-letter handling  
✅ Better for dev/test environments

### Migration Effort

- **Code Changes**: ~60 net new lines per service
- **Reused Code**: ~90% (all business logic unchanged)
- **Time Estimate**: 1-2 days per service
- **Risk**: Low (proven pattern, easy rollback)

## Recommendations

1. **Use Azure Functions for**:
   - Dev and test environments (massive cost savings)
   - Production with <200K messages/month
   - Services with irregular traffic patterns

2. **Keep Container Apps for**:
   - Production with >200K messages/month
   - Services requiring <100ms latency guarantee
   - Services with complex state management

3. **Hybrid Approach**:
   - Simple services (chunking, parsing, embedding) → Functions
   - Complex services (orchestrator) → Container Apps
   - Best of both worlds
