<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Azure-Optimized Images Quick Reference

## Quick Start

### 1. Use Pre-Built Images (Recommended)

Pull and use Azure-optimized images directly from GHCR:

```bash
# Pull Azure-optimized embedding service
docker pull ghcr.io/alan-jowett/copilot-for-consensus/embedding:azure

# Pull all Azure-optimized services
for service in auth chunking embedding ingestion orchestrator parsing reporting summarization ui gateway; do
  docker pull ghcr.io/alan-jowett/copilot-for-consensus/$service:azure
done
```

### 2. Deploy to Azure Container Apps

```bash
# Deploy with Azure-optimized images (default)
az deployment group create \
  --resource-group copilot-rg \
  --template-file infra/azure/main.bicep \
  --parameters @infra/azure/parameters.dev.json
  # containerImageTag is already set to "azure" in parameters files
```

### 3. Build Locally (Optional)

```bash
# Build embedding service
docker build -f embedding/Dockerfile.azure -t copilot-embedding:azure .

# Build all services
./scripts/build-azure-images.sh
```

## Image Tags

| Tag | Description | Size | Use Case |
|-----|-------------|------|----------|
| `azure` | Azure-optimized, latest | ~300-400 MB | **Production on Azure** |
| `azure-{sha}` | Azure-optimized, pinned | ~300-400 MB | Production with version control |
| `latest` | Local dev, latest | ~500-4500 MB | Local development |
| `{sha}` | Local dev, pinned | ~500-4500 MB | Development testing |

## Environment Variables

### Required for All Azure Images

```bash
# Azure Cosmos DB (MongoDB API)
DOCUMENT_DATABASE_HOST=your-cosmos.mongo.cosmos.azure.com
DOCUMENT_DATABASE_PORT=10255
DOCUMENT_DATABASE_NAME=copilot

# Azure Service Bus
MESSAGE_BUS_TYPE=servicebus
MESSAGE_BUS_HOST=your-servicebus.servicebus.windows.net

# Azure Blob Storage
ARCHIVE_STORE_TYPE=azure_blob
AZURE_STORAGE_ACCOUNT=your-storage-account
AZURE_STORAGE_CONTAINER=archives
```

### For Embedding Service

```bash
EMBEDDING_BACKEND=azure
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_KEY=<from-managed-identity-or-key-vault>
```

### For Summarization & Orchestrator

```bash
LLM_BACKEND=azure
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_KEY=<from-managed-identity-or-key-vault>
```

## Size Comparison Cheat Sheet

```
Local Images (Total: ~8.7 GB)
├── embedding:      4.5 GB (PyTorch base)
├── summarization:  800 MB
├── reporting:      750 MB
├── orchestrator:   500 MB
├── parsing:        500 MB
├── chunking:       500 MB
├── ingestion:      550 MB
├── auth:           450 MB
├── ui:             150 MB
└── gateway:         50 MB

Azure Images (Total: ~2.7 GB) - 69% reduction
├── embedding:      400 MB ⬇️ 90%
├── summarization:  350 MB ⬇️ 56%
├── reporting:      380 MB ⬇️ 49%
├── orchestrator:   300 MB ⬇️ 40%
├── parsing:        300 MB ⬇️ 40%
├── chunking:       300 MB ⬇️ 40%
├── ingestion:      320 MB ⬇️ 42%
├── auth:           280 MB ⬇️ 38%
├── ui:              45 MB ⬇️ 70%
└── gateway:         45 MB ⬇️ 10%
```

## Troubleshooting Quick Fixes

### "Model not found" Error

```bash
# Check environment variables
az containerapp show \
  --name copilot-embedding-dev \
  --resource-group copilot-rg \
  --query properties.template.containers[0].env

# Fix: Update to Azure OpenAI
az containerapp update \
  --name copilot-embedding-dev \
  --resource-group copilot-rg \
  --set-env-vars \
    EMBEDDING_BACKEND=azure \
    AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
```

### "403 Forbidden" from Azure OpenAI

```bash
# Check managed identity has Cognitive Services OpenAI User role
az role assignment list \
  --assignee <managed-identity-id> \
  --scope <azure-openai-resource-id> \
  --query "[?roleDefinitionName=='Cognitive Services OpenAI User']"
```

### Slow Image Pull

```bash
# Import to Azure Container Registry for faster pulls
az acr import \
  --name your-acr \
  --source ghcr.io/alan-jowett/copilot-for-consensus/embedding:azure \
  --image copilot/embedding:azure
```

## Key Differences Summary

| Feature | Local Images | Azure Images |
|---------|--------------|--------------|
| **Base** | pytorch/pytorch (4.2GB) | python:3.11-slim (150MB) |
| **Embeddings** | SentenceTransformers | Azure OpenAI API |
| **LLM** | Ollama/llama.cpp | Azure OpenAI GPT-4o |
| **Storage** | Local filesystem | Azure Blob Storage |
| **Message Queue** | Local RabbitMQ | Azure Service Bus |
| **Database** | Local MongoDB | Azure Cosmos DB |
| **Deployment** | docker-compose | Azure Container Apps |
| **Size** | ~8.7 GB total | ~2.7 GB total |

## See Also

- [Full Documentation](./AZURE_OPTIMIZED_IMAGES.md) - Detailed guide
- [Azure Deployment Guide](../infra/azure/README.md) - Complete Azure setup
- [GitHub Actions Workflow](../.github/workflows/publish-docker-images-azure.yml) - CI/CD automation

---

**License**: MIT  
**Copyright**: © 2025 Copilot-for-Consensus contributors
