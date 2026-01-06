# Chunking Azure Function

Proof-of-concept implementation of the chunking service as an Azure Function with Service Bus trigger.

## Overview

This function replaces the chunking Container App service with a serverless Azure Function that:
- Listens to the `json.parsed` Service Bus queue
- Processes messages to split long email bodies into semantic chunks
- Publishes `chunks.prepared` events to the message bus
- Stores chunks in Cosmos DB

## Architecture

```
Service Bus (json.parsed) → Azure Function → Cosmos DB + Service Bus (chunks.prepared)
```

### Key Differences from Container App

| Aspect | Container App | Azure Function |
|--------|--------------|----------------|
| **Trigger** | Manual Service Bus consumer | Service Bus trigger binding |
| **HTTP Server** | FastAPI + Uvicorn | None (event-driven only) |
| **Health Endpoint** | `/health` | Built-in (handled by platform) |
| **Scaling** | Manual configuration | Automatic based on queue depth |
| **Cost** | Always-on (~$29/month) | Pay-per-execution (~$0.20/month) |

## Local Development

### Prerequisites

1. **Azure Functions Core Tools v4**
   ```bash
   npm install -g azure-functions-core-tools@4
   ```

2. **Python 3.11**
   ```bash
   python --version  # Should be 3.11.x
   ```

3. **Azurite** (Storage Emulator)
   ```bash
   npm install -g azurite
   # Or use Docker
   docker run -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite
   ```

4. **Running Infrastructure** (MongoDB, RabbitMQ, or Azure Service Bus)

### Setup

1. **Create virtual environment**
   ```bash
   cd functions/chunking_function
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure local settings**
   
   Copy `local.settings.json.example` to `local.settings.json` and update values:
   
   ```json
   {
     "Values": {
       "AzureWebJobsServiceBus": "Endpoint=sb://...",
       "DOC_STORE_HOST": "localhost",
       "DOC_STORE_PORT": "27017",
       "MESSAGE_BUS_HOST": "localhost",
       "MESSAGE_BUS_PORT": "5672"
     }
   }
   ```

4. **Start Azurite** (in separate terminal)
   ```bash
   azurite --silent --location /tmp/azurite --debug /tmp/azurite-debug.log
   ```

5. **Start the function**
   ```bash
   func start
   ```

### Testing Locally

1. **Send a test message** to the `json.parsed` queue:
   
   Using Azure Service Bus:
   ```bash
   # Using Azure CLI
   az servicebus queue send \
     --namespace-name <namespace> \
     --name json.parsed \
     --body '{"data": {"archive_id": "test-archive", "message_doc_ids": ["msg1", "msg2"]}}'
   ```
   
   Using RabbitMQ:
   ```bash
   # Using rabbitmqadmin
   rabbitmqadmin publish exchange=copilot.events routing_key=json.parsed \
     payload='{"data": {"archive_id": "test-archive", "message_doc_ids": ["msg1", "msg2"]}}'
   ```

2. **Monitor logs** in the terminal where `func start` is running

3. **Check results**:
   - Chunks should be created in Cosmos DB/MongoDB
   - `chunks.prepared` event should be published to message bus

## Deployment

### Using Azure CLI

```bash
# Deploy infrastructure (Function App)
az deployment group create \
  --resource-group <rg-name> \
  --template-file ../../infra/azure/modules/functions.bicep \
  --parameters projectName=copilot environment=dev ...

# Deploy function code
func azure functionapp publish copilot-func-dev
```

### Using GitHub Actions

The `.github/workflows/deploy-functions.yml` workflow automatically deploys on push to main:

```bash
git add .
git commit -m "Update chunking function"
git push origin main
```

Or trigger manually:
```bash
gh workflow run deploy-functions.yml -f environment=dev
```

## Configuration

### Environment Variables

All configuration is loaded from Function App settings (environment variables):

| Variable | Description | Example |
|----------|-------------|---------|
| `DOC_STORE_TYPE` | Document store type | `azurecosmos` or `mongodb` |
| `DOC_STORE_HOST` | Cosmos DB / MongoDB host | `account.documents.azure.com` |
| `MESSAGE_BUS_TYPE` | Message bus type | `azureservicebus` or `rabbitmq` |
| `MESSAGE_BUS_HOST` | Service Bus / RabbitMQ host | `namespace.servicebus.windows.net` |
| `CHUNKING_STRATEGY` | Chunking algorithm | `sentence` |
| `CHUNK_SIZE` | Target chunk size (tokens) | `512` |
| `CHUNK_OVERLAP` | Overlap between chunks (tokens) | `50` |

See `local.settings.json` for full list.

### Managed Identity

In Azure, the function uses Managed Identity to authenticate to:
- Azure Service Bus (trigger and publisher)
- Azure Cosmos DB (document store)
- Azure Key Vault (secrets)

No connection strings or passwords needed in Azure!

## Monitoring

### Application Insights

Functions automatically emit telemetry to Application Insights:

**View in Azure Portal:**
1. Navigate to Function App → Application Insights
2. Query logs with Kusto (KQL):
   ```kql
   traces
   | where message contains "Chunking"
   | order by timestamp desc
   | take 100
   ```

**Monitor execution metrics:**
- Invocation count
- Success/failure rate
- Execution duration
- Cold start frequency

### Custom Metrics

The function reuses the existing Prometheus metrics from the Container App version:
- `chunking_messages_processed_total`
- `chunking_chunks_created_total`
- `chunking_duration_seconds`

These can be pushed to Pushgateway or exported to Application Insights custom metrics.

## Performance

| Metric | Value |
|--------|-------|
| **Cold Start** | ~3 seconds (includes service initialization) |
| **Warm Start** | <100ms |
| **Processing Time** | ~2 seconds (same as Container App) |
| **Max Throughput** | ~500 messages/minute (with auto-scaling) |

## Troubleshooting

### Function won't start locally

**Error**: `Storage account connection string is invalid`

**Solution**: Start Azurite storage emulator first:
```bash
azurite --silent
```

### Messages not being processed

**Check**:
1. Function is listening to correct queue name: `json.parsed`
2. Service Bus connection string is correct
3. Messages are in correct format (JSONParsed event schema)
4. Check function logs for errors

### Cold starts are too slow

**Options**:
1. Use Premium Plan (EP1) - eliminates cold starts (~$150/month)
2. Optimize service initialization (lazy load heavy dependencies)
3. Reduce package size (fewer dependencies)

### Monitoring is different from Container Apps

**Solution**: Use hybrid monitoring approach:
- Application Insights for Functions
- Prometheus/Grafana for Container Apps
- Unified Grafana dashboard querying both

## Cost Optimization

### Current Costs (Consumption Plan)

At 1,000 messages/day (~30K/month):
- Execution cost: ~$0.20/month
- Storage cost: ~$5/month (shared across functions)
- **Total**: ~$5.20/month vs $29/month for Container App

### Tips to Reduce Costs

1. **Configure sampling** to reduce Application Insights data:
   ```json
   {
     "logging": {
       "applicationInsights": {
         "samplingSettings": {
           "isEnabled": true,
           "maxTelemetryItemsPerSecond": 5
         }
       }
     }
   }
   ```

2. **Batch processing**: Group multiple messages in one invocation (if possible)

3. **Adjust timeout**: Reduce `functionTimeout` if processing is fast

4. **Use Premium Plan for high volume**: Breakeven at ~250K messages/month

## Next Steps

After successful pilot with chunking function:

1. **Implement parsing function** (similar pattern)
2. **Implement embedding function** (similar pattern)
3. **Evaluate orchestrator** (may need Durable Functions for state)
4. **Evaluate summarization** (LLM latency considerations)

## References

- [Azure Functions Service Bus Trigger](https://learn.microsoft.com/azure/azure-functions/functions-bindings-service-bus-trigger)
- [Azure Functions Python Developer Guide](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)
- [Application Insights for Functions](https://learn.microsoft.com/azure/azure-functions/functions-monitoring)
- [Parent Investigation Document](../../docs/AZURE_FUNCTIONS_INVESTIGATION.md)
