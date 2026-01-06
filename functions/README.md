# Azure Functions Proof-of-Concept

This directory contains proof-of-concept implementations of message consumer services as Azure Functions.

## Overview

This investigation explores migrating event-driven message consumer services from Azure Container Apps to Azure Functions for cost optimization and automatic scaling.

## Services

### Chunking Function (`chunking_function/`)

Proof-of-concept implementation of the chunking service as an Azure Function with Service Bus trigger.

**Key Changes from Container App:**
- Service Bus trigger binding instead of manual message consumption
- Azure Functions runtime instead of FastAPI/Uvicorn
- Application Insights for logging (vs Prometheus/Grafana)
- Simplified deployment and scaling configuration

## Architecture

```
Azure Service Bus Queue → Function (Service Bus Trigger) → Process Message → Publish Event
```

### Benefits

1. **Cost Optimization**: Pay-per-execution pricing (~60-80% savings in dev/test)
2. **Automatic Scaling**: Scales with queue depth automatically
3. **Scale-to-Zero**: No cost when idle
4. **Simplified Infrastructure**: No Container Apps environment needed

### Trade-offs

1. **Cold Start Latency**: 1-5 seconds for Python functions
2. **Monitoring Changes**: Application Insights vs Prometheus/Grafana
3. **Development Model**: Different local testing approach
4. **Runtime Constraints**: Azure Functions-specific limitations

## Local Development

### Prerequisites

```bash
# Install Azure Functions Core Tools
npm install -g azure-functions-core-tools@4

# Or on Linux
wget -q https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install azure-functions-core-tools-4
```

### Running Locally

```bash
cd functions/chunking_function
func start
```

## Deployment

See `../infra/azure/modules/functions.bicep` for Infrastructure-as-Code deployment.

## Investigation Findings

See `AZURE_FUNCTIONS_INVESTIGATION.md` in the docs directory for detailed analysis, cost comparisons, and recommendations.
