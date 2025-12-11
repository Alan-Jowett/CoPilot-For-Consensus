<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Embedding Provider Usage Guide

This guide demonstrates how to use the embedding provider abstraction layer.

**Note:** The embedding provider implementation has been moved to the `copilot_embedding` SDK module located in `adapter/copilot_embedding/`. This allows it to be shared across multiple services.

## Installation

First, install the SDK module:

```bash
# Basic installation
pip install ./adapter/copilot_embedding

# With specific backend support
pip install "./adapter/copilot_embedding[sentencetransformers]"  # For local models
pip install "./adapter/copilot_embedding[openai]"                 # For OpenAI/Azure
pip install "./adapter/copilot_embedding[huggingface]"            # For HuggingFace
pip install "./adapter/copilot_embedding[all]"                    # For all backends
```

## Quick Start

### Using the Factory Method

The easiest way to create an embedding provider is using the factory method with environment variables:

```python
from copilot_embedding import create_embedding_provider

# Uses environment variables to select and configure provider
provider = create_embedding_provider()
embedding = provider.embed("Your text here")
```

### Environment Variables

Set these environment variables to configure the provider:

```bash
# Select backend (default: sentencetransformers)
export EMBEDDING_BACKEND=sentencetransformers  # or mock, openai, azure, huggingface

# For SentenceTransformers (local)
export EMBEDDING_MODEL=all-MiniLM-L6-v2
export DEVICE=cpu  # or cuda, mps
export MODEL_CACHE_DIR=/path/to/cache

# For OpenAI
export EMBEDDING_BACKEND=openai
export OPENAI_API_KEY=your-api-key
export EMBEDDING_MODEL=text-embedding-ada-002

# For Azure OpenAI
export EMBEDDING_BACKEND=azure
export AZURE_OPENAI_KEY=your-api-key
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_OPENAI_DEPLOYMENT=text-embedding-ada-002

# For HuggingFace Transformers
export EMBEDDING_BACKEND=huggingface
export EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
export DEVICE=cpu

# For Testing
export EMBEDDING_BACKEND=mock
export EMBEDDING_DIMENSION=384
```

## Provider Examples

### 1. Mock Provider (for Testing)

```python
from copilot_embedding import MockEmbeddingProvider

provider = MockEmbeddingProvider(dimension=384)
embedding = provider.embed("Test text")
# Returns deterministic mock embeddings based on text hash
```

### 2. SentenceTransformers (Local, Offline)

```python
from copilot_embedding import SentenceTransformerEmbeddingProvider

provider = SentenceTransformerEmbeddingProvider(
    model_name="all-MiniLM-L6-v2",
    device="cpu",
    cache_dir="/path/to/cache"
)
embedding = provider.embed("Your text here")
```

**Popular Models:**
- `all-MiniLM-L6-v2` (384 dimensions, fast)
- `all-mpnet-base-v2` (768 dimensions, better quality)
- `multi-qa-mpnet-base-cos-v1` (768 dimensions, optimized for Q&A)

### 3. OpenAI API

```python
from copilot_embedding import OpenAIEmbeddingProvider

provider = OpenAIEmbeddingProvider(
    api_key="your-openai-api-key",
    model="text-embedding-ada-002"
)
embedding = provider.embed("Your text here")
```

### 4. Azure OpenAI

```python
from copilot_embedding import OpenAIEmbeddingProvider

provider = OpenAIEmbeddingProvider(
    api_key="your-azure-api-key",
    model="text-embedding-ada-002",
    api_base="https://your-resource.openai.azure.com/",
    api_version="2023-05-15",
    deployment_name="your-deployment-name"
)
embedding = provider.embed("Your text here")
```

### 5. HuggingFace Transformers

```python
from copilot_embedding import HuggingFaceEmbeddingProvider

provider = HuggingFaceEmbeddingProvider(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    device="cpu",
    cache_dir="/path/to/cache",
    max_length=512
)
embedding = provider.embed("Your text here")
```

## Using with Factory and Parameters

You can also pass parameters directly to the factory:

```python
from copilot_embedding import create_embedding_provider

# Mock provider
provider = create_embedding_provider(backend="mock", dimension=128)

# SentenceTransformers with custom model
provider = create_embedding_provider(
    backend="sentencetransformers",
    model="all-mpnet-base-v2",
    device="cuda"
)

# OpenAI with custom key
provider = create_embedding_provider(
    backend="openai",
    api_key="your-key",
    model="text-embedding-ada-002"
)

# Azure OpenAI
provider = create_embedding_provider(
    backend="azure",
    api_key="your-key",
    api_base="https://your-resource.openai.azure.com/",
    deployment_name="your-deployment"
)
```

## Interface

All providers implement the same interface:

```python
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embeddings for the given text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        pass
```

This allows you to switch between providers without changing your downstream code.

## Best Practices

1. **Use Mock Provider for Tests**: Fast and deterministic
2. **Use SentenceTransformers for Local/Offline**: No API costs, works offline
3. **Use OpenAI/Azure for Production**: Higher quality, but requires API access
4. **Use HuggingFace for Custom Models**: Maximum flexibility

## Performance Considerations

- **Mock**: Instant (no actual computation)
- **SentenceTransformers**: ~10-50ms per text on CPU, ~1-5ms on GPU
- **OpenAI/Azure**: ~100-500ms (depends on network and API load)
- **HuggingFace**: ~20-100ms per text on CPU, ~2-10ms on GPU

## Batch Processing

For batch processing, call `embed()` in a loop:

```python
texts = ["text1", "text2", "text3"]
embeddings = [provider.embed(text) for text in texts]
```

Note: Some providers (like SentenceTransformers) support native batch processing which is more efficient. This could be added as an extension method in the future.
