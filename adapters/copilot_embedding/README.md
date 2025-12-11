# Copilot Embedding Provider SDK

A shared library for embedding generation with support for multiple backends including OpenAI, Azure OpenAI, local models, and test mocks.

## Features

- **Abstract Interface**: `EmbeddingProvider` base class for consistent API
- **Multiple Backends**:
  - `MockEmbeddingProvider`: Deterministic embeddings for testing
  - `SentenceTransformerEmbeddingProvider`: Local sentence-transformers models
  - `OpenAIEmbeddingProvider`: OpenAI and Azure OpenAI API support
  - `HuggingFaceEmbeddingProvider`: Raw HuggingFace Transformers models
- **Factory Pattern**: Easy provider selection via environment variables
- **Optional Dependencies**: Install only what you need for your chosen backend

## Installation

### Basic Installation

```bash
pip install ./adapter/copilot_embedding
```

### With Optional Backends

```bash
# For SentenceTransformers (local models)
pip install "./adapter/copilot_embedding[sentencetransformers]"

# For OpenAI/Azure OpenAI
pip install "./adapter/copilot_embedding[openai]"

# For HuggingFace Transformers
pip install "./adapter/copilot_embedding[huggingface]"

# For all backends
pip install "./adapter/copilot_embedding[all]"
```

## Quick Start

### Using the Factory Method

```python
from copilot_embedding import create_embedding_provider

# Create a provider using environment variables
provider = create_embedding_provider()
embedding = provider.embed("Your text here")

# Create a mock provider for testing
test_provider = create_embedding_provider(backend="mock", dimension=128)
embedding = test_provider.embed("Test text")
```

### Environment Variables

```bash
# Select backend (default: sentencetransformers)
export EMBEDDING_BACKEND=mock  # or sentencetransformers, openai, azure, huggingface

# For mock provider
export EMBEDDING_DIMENSION=384

# For SentenceTransformers
export EMBEDDING_MODEL=all-MiniLM-L6-v2
export DEVICE=cpu  # or cuda, mps

# For OpenAI
export OPENAI_API_KEY=your-api-key
export EMBEDDING_MODEL=text-embedding-ada-002

# For Azure OpenAI
export AZURE_OPENAI_KEY=your-api-key
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_OPENAI_DEPLOYMENT=your-deployment-name
```

### Direct Provider Usage

```python
from copilot_embedding import (
    MockEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    OpenAIEmbeddingProvider,
)

# Mock provider (for testing)
mock_provider = MockEmbeddingProvider(dimension=384)
embedding = mock_provider.embed("Test text")

# SentenceTransformers (local, offline)
st_provider = SentenceTransformerEmbeddingProvider(
    model_name="all-MiniLM-L6-v2",
    device="cpu"
)
embedding = st_provider.embed("Your text")

# OpenAI
openai_provider = OpenAIEmbeddingProvider(
    api_key="your-api-key",
    model="text-embedding-ada-002"
)
embedding = openai_provider.embed("Your text")
```

## Interface

All providers implement the `EmbeddingProvider` interface:

```python
from abc import ABC, abstractmethod
from typing import List

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

## Development

### Running Tests

```bash
cd adapter/copilot_embedding
pytest tests/ -v
```

### Running Tests with Coverage

```bash
cd adapter/copilot_embedding
pytest tests/ --cov=copilot_embedding --cov-report=html
```

## License

MIT License - See LICENSE file for details
