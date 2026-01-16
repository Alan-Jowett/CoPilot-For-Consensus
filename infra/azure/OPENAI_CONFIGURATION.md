<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Azure OpenAI Configuration Guide

This document provides detailed guidance on configuring Azure OpenAI for Copilot for Consensus deployments.

## Overview

The Azure deployment supports optional integration with Azure OpenAI for:
- **GPT-4o** model for summarization and orchestration
- **Text embedding models** (ada-002, text-embedding-3-small, text-embedding-3-large) for semantic search

When Azure OpenAI is disabled, services automatically fall back to local alternatives:
- GPT-4o → Ollama with Mistral/Llama models
- Text embeddings → SentenceTransformers with all-MiniLM-L6-v2

## Quick Start

### Enable Azure OpenAI (Default)

Set in your parameter file (e.g., `parameters.dev.json`):

```json
{
  "deployAzureOpenAI": { "value": true }
}
```

### Disable Azure OpenAI (Use Local Models)

```json
{
  "deployAzureOpenAI": { "value": false }
}
```

## Configuration Parameters

### Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `deployAzureOpenAI` | bool | `true` | Deploy Azure OpenAI resource |
| `azureOpenAISku` | string | `S0` | Azure OpenAI SKU (only S0 supported) |
| `azureOpenAIDeploymentSku` | string | `GlobalStandard` | Deployment SKU (Standard or GlobalStandard) |
| `azureOpenAIModelVersion` | string | `2024-11-20` | GPT-4o model version |
| `azureOpenAIDeploymentCapacity` | int | `10` | TPM capacity (1000 tokens/min per unit) |

### Embedding Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `deployAzureOpenAIEmbeddingModel` | bool | `true` | Deploy embedding model |
| `azureOpenAIEmbeddingModelName` | string | `text-embedding-ada-002` | Embedding model choice |
| `azureOpenAIEmbeddingDeploymentCapacity` | int | `10` | TPM capacity for embeddings |

### Network Security

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `azureOpenAIAllowedCidrs` | array | `[]` | IP CIDR allowlist for Azure OpenAI access |

## Model Selection

### GPT-4o Versions

| Version | Release Date | Status | Recommended For |
|---------|--------------|--------|-----------------|
| `2024-11-20` | Nov 2024 | Latest GA | Production |
| `2024-08-06` | Aug 2024 | Stable | Conservative deployments |
| `2024-05-13` | May 2024 | Stable | Legacy compatibility |

### Embedding Models

| Model | Dimensions | Cost | Quality | Use Case |
|-------|------------|------|---------|----------|
| `text-embedding-ada-002` | 1536 | Medium | High | General purpose (recommended) |
| `text-embedding-3-small` | 1536 | Lower | Good | Cost-optimized deployments |
| `text-embedding-3-large` | 3072 | Higher | Highest | Maximum accuracy |

## Deployment SKUs

### Standard vs GlobalStandard

**Standard SKU**:
- Regional deployment
- Lower cost
- Fixed capacity in single region
- Suitable for dev/test

**GlobalStandard SKU** (Recommended for Production):
- Global load balancing across regions
- Higher availability
- Automatic failover
- Better performance under load

Example configuration:

```json
{
  "azureOpenAIDeploymentSku": { "value": "GlobalStandard" },
  "azureOpenAIDeploymentCapacity": { "value": 50 }
}
```

## Capacity Planning

### Tokens Per Minute (TPM)

Each capacity unit = 1,000 TPM (tokens per minute).

**Development**:
- GPT-4o: 10 units (10K TPM)
- Embeddings: 10 units (10K TPM)
- Cost: ~$50-100/month

**Staging**:
- GPT-4o: 20 units (20K TPM)
- Embeddings: 20 units (20K TPM)
- Cost: ~$100-200/month

**Production**:
- GPT-4o: 50-100 units (50K-100K TPM)
- Embeddings: 50 units (50K TPM)
- Cost: ~$250-500/month

## Security Configuration

### API Key Management

API keys are automatically:
1. Retrieved from Azure OpenAI using `listKeys()` API
2. Stored in the **Core Key Vault** as `azure-openai-api-key`
3. Mirrored into the **Environment Key Vault** used by the services (the vault referenced by `AZURE_KEY_VAULT_NAME`)
4. Never exposed in plaintext environment variables

### Network Access Control

**Development** (`environment: dev`):
```json
{
  "azureOpenAIAllowedCidrs": {
    "value": [
      "YOUR_DEV_IP/32"
    ]
  }
}
```

**Production** (`environment: prod`):
- Public endpoint disabled
- Requires Private Link (future enhancement)
- VNet integration with Container Apps

## Service Integration

### Automatic Backend Selection

Services detect Azure OpenAI availability and automatically configure:

**When Azure OpenAI is enabled**:
- `LLM_BACKEND=azure`
- `EMBEDDING_BACKEND=azure`
- `AZURE_OPENAI_ENDPOINT=https://your-account.openai.azure.com/`
- `AZURE_OPENAI_DEPLOYMENT=gpt-4o-deployment` (or `embedding-deployment`)
- `AZURE_OPENAI_KEY=@Microsoft.KeyVault(SecretUri=...)`

**When Azure OpenAI is disabled**:
- `LLM_BACKEND=ollama`
- `EMBEDDING_BACKEND=sentencetransformers`
- Local model inference (no API keys required)

### Affected Services

1. **Orchestrator Service**
   - Uses GPT-4o for orchestration logic
   - Falls back to Ollama when Azure OpenAI disabled

2. **Summarization Service**
   - Uses GPT-4o for thread/weekly summaries
   - Falls back to Ollama when Azure OpenAI disabled

3. **Embedding Service**
   - Uses text-embedding-ada-002 (or 3-small/3-large) for embeddings
   - Falls back to SentenceTransformers when Azure OpenAI disabled

## Example Configurations

### Development (Local Models)

```json
{
  "environment": { "value": "dev" },
  "deployAzureOpenAI": { "value": false }
}
```

Services use:
- Ollama with Mistral-7B (LLM)
- SentenceTransformers with all-MiniLM-L6-v2 (embeddings)

### Development (Azure OpenAI)

```json
{
  "environment": { "value": "dev" },
  "deployAzureOpenAI": { "value": true },
  "azureOpenAIDeploymentSku": { "value": "Standard" },
  "azureOpenAIDeploymentCapacity": { "value": 10 },
  "deployAzureOpenAIEmbeddingModel": { "value": true },
  "azureOpenAIEmbeddingModelName": { "value": "text-embedding-ada-002" },
  "azureOpenAIEmbeddingDeploymentCapacity": { "value": 10 }
}
```

### Staging

```json
{
  "environment": { "value": "staging" },
  "deployAzureOpenAI": { "value": true },
  "azureOpenAIDeploymentSku": { "value": "GlobalStandard" },
  "azureOpenAIModelVersion": { "value": "2024-11-20" },
  "azureOpenAIDeploymentCapacity": { "value": 20 },
  "deployAzureOpenAIEmbeddingModel": { "value": true },
  "azureOpenAIEmbeddingModelName": { "value": "text-embedding-ada-002" },
  "azureOpenAIEmbeddingDeploymentCapacity": { "value": 20 }
}
```

### Production

```json
{
  "environment": { "value": "prod" },
  "deployAzureOpenAI": { "value": true },
  "azureOpenAIDeploymentSku": { "value": "GlobalStandard" },
  "azureOpenAIModelVersion": { "value": "2024-11-20" },
  "azureOpenAIDeploymentCapacity": { "value": 50 },
  "deployAzureOpenAIEmbeddingModel": { "value": true },
  "azureOpenAIEmbeddingModelName": { "value": "text-embedding-3-large" },
  "azureOpenAIEmbeddingDeploymentCapacity": { "value": 50 }
}
```

### Embeddings-Only (No LLM)

```json
{
  "environment": { "value": "dev" },
  "deployAzureOpenAI": { "value": true },
  "deployAzureOpenAIEmbeddingModel": { "value": true },
  "azureOpenAIEmbeddingModelName": { "value": "text-embedding-ada-002" }
}
```

Note: GPT-4o deployment is always included when `deployAzureOpenAI: true`. To use embeddings without GPT-4o, deploy Azure OpenAI and set orchestrator/summarization services to use Ollama via service-specific env vars (future enhancement).

## Deployment Outputs

After deployment, the following outputs are available:

```bicep
output openaiAccountName string              // Azure OpenAI account name
output openaiAccountEndpoint string          // API endpoint (e.g., https://account.openai.azure.com/)
output openaiGpt4DeploymentName string       // GPT-4o deployment name
output openaiEmbeddingDeploymentName string  // Embedding deployment name (if enabled)
```

Use these outputs for manual configuration or post-deployment automation.

## Troubleshooting

### Deployment Fails with "Quota Exceeded"

Azure OpenAI has quota limits per subscription and region.

**Solution**:
1. Request quota increase via Azure Portal
2. Try different region with available quota
3. Reduce `azureOpenAIDeploymentCapacity`

### Services Can't Connect to Azure OpenAI

**Check**:
1. Azure OpenAI `networkDefaultAction` is `Deny` by default
2. Add your IP to `azureOpenAIAllowedCidrs`
3. For dev environment, public access is enabled but requires IP allowlist

### API Key Not Found

**Check**:
1. Key Vault secret `azure-openai-api-key` exists in the vault your services are configured to use (`AZURE_KEY_VAULT_NAME`)
2. Container App managed identities have "Key Vault Secrets User" role on that Key Vault
3. Key Vault public access enabled (or Private Link configured)

## Cost Management

### Estimate Costs

Use [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/) for OpenAI:
- GPT-4o: ~$0.03/1K tokens (input), ~$0.06/1K tokens (output)
- text-embedding-ada-002: ~$0.0001/1K tokens

### Cost Optimization Tips

1. **Use local models for dev**: Set `deployAzureOpenAI: false`
2. **Reduce capacity**: Start with 10 units, scale up as needed
3. **Use Standard SKU for dev**: Only use GlobalStandard for production
4. **Choose efficient embedding models**: text-embedding-3-small for cost savings
5. **Monitor usage**: Set up budget alerts in Azure Cost Management

## Migration from Local to Azure OpenAI

To switch from local models to Azure OpenAI without redeployment:

1. Deploy Azure OpenAI resource separately:
   ```bash
   az deployment group create --resource-group copilot-rg --template-file modules/openai.bicep --parameters ...
   ```

2. Update Container Apps environment variables:
   ```bash
   az containerapp update --name copilot-orchestrator --resource-group copilot-rg \
     --set-env-vars LLM_BACKEND=azure AZURE_OPENAI_ENDPOINT=https://... AZURE_OPENAI_KEY=...
   ```

3. Restart services:
   ```bash
   az containerapp revision restart --app copilot-orchestrator --resource-group copilot-rg
   ```

## References

- [Azure OpenAI Service Documentation](https://learn.microsoft.com/azure/cognitive-services/openai/)
- [GPT-4o Model Documentation](https://learn.microsoft.com/azure/cognitive-services/openai/concepts/models#gpt-4o)
- [Embedding Models Documentation](https://learn.microsoft.com/azure/cognitive-services/openai/concepts/models#embeddings)
- [Main Deployment Guide](README.md)
- [Bicep Architecture](BICEP_ARCHITECTURE.md)

---

**Last Updated**: 2025-12-31
**License**: MIT
**Copyright**: © 2025 Copilot-for-Consensus contributors
