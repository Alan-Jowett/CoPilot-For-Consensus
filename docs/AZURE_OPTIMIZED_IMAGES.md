<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Azure-Optimized Docker Images

This document describes the Azure-optimized Docker images for Copilot-for-Consensus, designed specifically for deployment to Azure Container Apps and other Azure services.

## Overview

The Azure-optimized images are **significantly smaller and more efficient** than the standard local development images, with optimizations including:

- **Excludes local LLM models and runtimes** (Ollama, llama.cpp)
- **Lighter base images** (uses `python:3.11-slim` instead of `pytorch/pytorch`)
- **Production-only dependencies** (excludes development and testing packages)
- **Azure-native integrations** (Azure OpenAI, Azure Blob Storage, Azure AI Search)
- **Multi-stage builds** where applicable to minimize final image size

## Image Size Comparison

| Service | Local Image | Azure Image | Savings |
|---------|-------------|-------------|---------|
| **embedding** | ~4.5 GB (PyTorch base) | ~400 MB | **~90%** |
| **summarization** | ~800 MB | ~350 MB | **~56%** |
| **reporting** | ~750 MB | ~380 MB | **~49%** |
| **orchestrator** | ~500 MB | ~300 MB | **~40%** |
| **parsing** | ~500 MB | ~300 MB | **~40%** |
| **chunking** | ~500 MB | ~300 MB | **~40%** |
| **ingestion** | ~550 MB | ~320 MB | **~42%** |
| **auth** | ~450 MB | ~280 MB | **~38%** |
| **ui** | ~150 MB | ~45 MB | **~70%** |
| **gateway** | ~50 MB | ~45 MB | **~10%** |

**Overall savings**: Reduces total Docker image footprint from **~8.7 GB to ~2.7 GB (~69% reduction)**.

## Key Differences from Local Images

### 1. Embedding Service
**Local (`Dockerfile`):**
- Base: `pytorch/pytorch` (~4.2 GB)
- Includes: PyTorch, SentenceTransformers, local model files
- Backend: `sentencetransformers` (local inference)

**Azure (`Dockerfile.azure`):**
- Base: `python:3.11-slim` (~150 MB)
- Excludes: PyTorch, SentenceTransformers, local models
- Backend: `openai` (Azure OpenAI Embeddings API)
- Models: Fetched from Azure OpenAI (e.g., `text-embedding-3-small` or `text-embedding-3-large`; `text-embedding-ada-002` is legacy and not recommended for new deployments)

### 2. Summarization Service
**Local (`Dockerfile`):**
- Includes: Ollama client, llama.cpp client libraries
- Backend: `ollama` or `llamacpp` (local inference)

**Azure (`Dockerfile.azure`):**
- Excludes: Local LLM client libraries
- Backend: `azure` (Azure OpenAI GPT-4o API)
- Models: Accessed via Azure OpenAI endpoint

### 3. Reporting Service
**Local (`Dockerfile`):**
- Includes: Local embedding models for search

**Azure (`Dockerfile.azure`):**
- Uses: Azure OpenAI Embeddings API for semantic search
- Vectorstore: Qdrant or Azure AI Search

### 4. All Services
**Local (`Dockerfile`):**
- Includes: Full adapter dependencies, local storage, local message queue

**Azure (`Dockerfile.azure`):**
- Uses: Azure Blob Storage, Azure Service Bus, Azure Cosmos DB
- Optimized: Minimal production dependencies only

## Building Azure-Optimized Images

### Prerequisites
- Docker with BuildKit enabled (Docker 20.10+)
- Azure Container Registry or GitHub Container Registry access

### Build Locally

Build a single service:
```bash
# Build embedding service with Azure optimizations
docker build \
  -f embedding/Dockerfile.azure \
  -t copilot-embedding:azure \
  .

# Build summarization service
docker build \
  -f summarization/Dockerfile.azure \
  -t copilot-summarization:azure \
  .
```

Build all Azure-optimized services:
```bash
# Build all services with azure tag
services=(auth chunking embedding ingestion orchestrator parsing reporting summarization)

for service in "${services[@]}"; do
  echo "Building $service..."
  docker build \
    -f "$service/Dockerfile.azure" \
    -t "copilot-$service:azure" \
    .
done

# Build UI and gateway
docker build -f ui/Dockerfile.azure -t copilot-ui:azure ui/
docker build -f infra/nginx/Dockerfile.azure -t copilot-gateway:azure infra/nginx/
```

### Build with GitHub Actions

The repository includes automated builds for Azure-optimized images. See [GitHub Actions Workflow](#github-actions-integration) below.

## Using Azure-Optimized Images

### With Azure Container Apps

The Azure Bicep templates (`infra/azure/main.bicep`) automatically reference Azure-optimized images when deploying to Azure:

```bicep
param containerImageTag string = 'azure'

// Container Apps will pull from:
// ghcr.io/alan-jowett/copilot-for-consensus/embedding:azure
// ghcr.io/alan-jowett/copilot-for-consensus/summarization:azure
// ... etc
```

### Environment Variables

Azure-optimized images require environment variables for Azure services:

**Embedding Service:**
```bash
EMBEDDING_BACKEND=azure
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=text-embedding-ada-002
AZURE_OPENAI_KEY=<from-key-vault>
```

**Summarization & Orchestrator Services:**
```bash
LLM_BACKEND=azure
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_KEY=<from-key-vault>
```

**All Services (Storage):**
```bash
# Use Azure Cosmos DB instead of local MongoDB
DOCUMENT_STORE_TYPE=mongodb
DOCUMENT_DATABASE_HOST=your-cosmos.mongo.cosmos.azure.com
DOCUMENT_DATABASE_PORT=10255
DOCUMENT_DATABASE_NAME=copilot

# Use Azure Service Bus instead of local RabbitMQ
MESSAGE_BUS_TYPE=servicebus
MESSAGE_BUS_HOST=your-servicebus.servicebus.windows.net

# Use Azure Blob Storage instead of local filesystem
ARCHIVE_STORE_TYPE=azure_blob
AZURE_STORAGE_ACCOUNT=your-storage-account
AZURE_STORAGE_CONTAINER=archives
```

## GitHub Actions Integration

### Automated Build and Push

The Azure-optimized images are automatically built and pushed to GitHub Container Registry when changes are merged to `main`.

**Workflow: `.github/workflows/publish-docker-images-azure.yml`**

```yaml
name: Publish Azure-Optimized Docker Images

on:
  push:
    branches: [main]
    paths:
      - '**/Dockerfile.azure'
      - 'adapters/**'
      - '.github/workflows/publish-docker-images-azure.yml'
  workflow_dispatch:

jobs:
  publish:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [auth, chunking, embedding, ingestion, orchestrator, parsing, reporting, summarization, ui, gateway]
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: docker/setup-buildx-action@v3
      
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ${{ matrix.service }}/Dockerfile.azure
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/${{ matrix.service }}:azure
            ghcr.io/${{ github.repository }}/${{ matrix.service }}:azure-${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Manual Trigger

Trigger a build manually from GitHub Actions:
1. Go to **Actions** tab
2. Select **Publish Azure-Optimized Docker Images**
3. Click **Run workflow**

## Deployment Guide

### 1. Deploy to Azure Container Apps

Using the Azure CLI:

```bash
# Set environment variables
RESOURCE_GROUP="copilot-rg"
LOCATION="eastus"
ENVIRONMENT="dev"

# Deploy using Azure-optimized images
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/azure/main.bicep \
  --parameters @infra/azure/parameters.$ENVIRONMENT.json \
  --parameters containerImageTag=azure
```

Using PowerShell:

```powershell
$ResourceGroup = "copilot-rg"
$Location = "eastus"
$Environment = "dev"

# Deploy using Azure-optimized images
az deployment group create `
  --resource-group $ResourceGroup `
  --template-file infra/azure/main.bicep `
  --parameters "@infra/azure/parameters.$Environment.json" `
  --parameters containerImageTag=azure
```

### 2. Verify Deployment

Check that containers are using Azure-optimized images:

```bash
# List container apps
az containerapp list \
  --resource-group $RESOURCE_GROUP \
  --query "[].{Name:name, Image:properties.template.containers[0].image}" \
  --output table

# Expected output:
# Name                    Image
# copilot-embedding-dev   ghcr.io/.../embedding:azure
# copilot-summarization-dev  ghcr.io/.../summarization:azure
# ...
```

### 3. Monitor Image Pull Times

Azure-optimized images pull **3-5x faster** than local images:

```bash
# Check container app revision status
az containerapp revision list \
  --resource-group $RESOURCE_GROUP \
  --name copilot-embedding-dev \
  --query "[0].{Status:properties.provisioningState, Created:properties.createdTime}" \
  --output table
```

## Cost Analysis

### Azure OpenAI API Costs

Using Azure OpenAI instead of local models incurs API costs:

**Embeddings (text-embedding-ada-002):**
- **Cost**: $0.10 per 1M tokens
- **Typical usage**: 10K emails/day × 500 tokens/email = 5M tokens/day
- **Monthly cost**: ~$15/month

**GPT-4o (summarization):**
- **Cost**: $5.00 per 1M input tokens, $15.00 per 1M output tokens
- **Typical usage**: 1K summaries/day × 2000 input + 500 output tokens
- **Monthly cost**: ~$525/month (input) + ~$225/month (output) = **~$750/month**

### Compute Cost Savings

Azure-optimized images reduce compute costs:

**Container Apps (per service):**
- **Local images**: 2 vCPU, 4 GB RAM (to handle PyTorch) = ~$60/month
- **Azure images**: 0.5 vCPU, 1 GB RAM (lighter workload) = ~$15/month
- **Savings per service**: ~$45/month

**Total compute savings** (10 services): ~$450/month

**Net additional cost at 1K summaries/day** (API costs - compute savings): **~$315/month; approximate break-even near ~15K requests/day**

For high-volume deployments (>50K requests/day), consider using Azure OpenAI Provisioned Throughput Units (PTU) for predictable pricing.

## Troubleshooting

### Issue: Container fails to start with "Model not found"

**Cause**: Service is configured for local model but using Azure-optimized image.

**Solution**: Ensure environment variables point to Azure OpenAI:
```bash
# Check container app environment
az containerapp show \
  --name copilot-embedding-dev \
  --resource-group copilot-rg \
  --query properties.template.containers[0].env

# Update environment variables if needed
az containerapp update \
  --name copilot-embedding-dev \
  --resource-group copilot-rg \
  --set-env-vars \
    EMBEDDING_BACKEND=azure \
    AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
```

### Issue: Image pull takes a long time

**Cause**: Pulling from wrong registry or network issues.

**Solution**: 
1. Verify image tag: `ghcr.io/alan-jowett/copilot-for-consensus/embedding:azure`
2. Check Container Apps network connectivity to GHCR
3. Use Azure Container Registry (ACR) for faster pulls in same region

### Issue: "403 Forbidden" when calling Azure OpenAI

**Cause**: Missing or invalid Azure OpenAI API key.

**Solution**: Verify managed identity has access to Azure OpenAI:
```bash
# Check identity assignments
az containerapp identity show \
  --name copilot-embedding-dev \
  --resource-group copilot-rg

# Verify RBAC role assignment
az role assignment list \
  --assignee <managed-identity-id> \
  --scope <azure-openai-resource-id>
```

Expected role: `Cognitive Services OpenAI User`

## Best Practices

### 1. Use Specific Image Tags

Don't use `:azure` in production; use commit SHA tags:
```bash
# Good (pinned version)
ghcr.io/alan-jowett/copilot-for-consensus/embedding:azure-abc123def456

# Bad (always pulls latest)
ghcr.io/alan-jowett/copilot-for-consensus/embedding:azure
```

### 2. Enable Image Caching

Use Azure Container Registry cache for faster pulls:
```bash
# Import images to ACR
az acr import \
  --name your-acr \
  --source ghcr.io/alan-jowett/copilot-for-consensus/embedding:azure \
  --image copilot/embedding:azure
```

### 3. Monitor API Usage

Set up Azure Monitor alerts for OpenAI API costs:
```bash
# Create budget alert
az consumption budget create \
  --budget-name copilot-openai-budget \
  --amount 1000 \
  --time-grain Monthly \
  --resource-group copilot-rg
```

### 4. Use Provisioned Throughput for High Volume

For >50K requests/day, use Azure OpenAI PTUs for cost savings:
```bash
# Deploy with provisioned throughput
az cognitiveservices account deployment create \
  --name your-openai \
  --resource-group copilot-rg \
  --deployment-name gpt-4o-provisioned \
  --model-name gpt-4o \
  --model-version 2024-11-20 \
  --sku-name ProvisionedManaged \
  --sku-capacity 100  # 100 PTUs
```

## Additional Resources

- [Azure Container Apps Documentation](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Azure OpenAI Service Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Docker Multi-Stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Copilot-for-Consensus Azure Deployment Guide](../infra/azure/README.md)

## Support

For issues with Azure-optimized images:
1. Check [Troubleshooting](#troubleshooting) section above
2. Review [GitHub Issues](https://github.com/Alan-Jowett/CoPilot-For-Consensus/issues)
3. Open a new issue with the `azure` and `docker` labels

---

**License**: MIT  
**Copyright**: © 2025 Copilot-for-Consensus contributors
