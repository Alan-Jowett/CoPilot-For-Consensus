<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot Vector Store

A modular abstraction layer for vector storage backends, enabling flexible switching between FAISS, in-memory, and future backends (Qdrant, Azure Cognitive Search).

## Features

- **Abstract Interface**: Common API for all vector store backends
- **Multiple Backends**:
  - `InMemoryVectorStore`: Simple in-memory storage for testing and development
  - `FAISSVectorStore`: Production-ready FAISS backend for efficient similarity search
  - `QdrantVectorStore`: Qdrant cloud/self-hosted vector database with persistence
  - `AzureAISearchVectorStore`: Azure AI Search (formerly Azure Cognitive Search) for cloud-native vector search
- **Factory Pattern**: Easy backend selection via config or environment variables
- **Type-Safe**: Full type hints for better IDE support and error detection
- **Well-Tested**: Comprehensive test coverage for all implementations

## Installation

### Basic Installation (In-Memory Only)

```bash
pip install -e adapters/copilot_vectorstore/
```

### With FAISS Support

```bash
pip install -e adapters/copilot_vectorstore/
pip install faiss-cpu  # or faiss-gpu for GPU support
```

### With Qdrant Support

```bash
pip install -e adapters/copilot_vectorstore/
pip install qdrant-client
```

Or use the extras:

```bash
pip install -e "adapters/copilot_vectorstore/[qdrant]"
```

### With Azure AI Search Support

```bash
pip install -e adapters/copilot_vectorstore/
pip install azure-search-documents azure-identity
```

Or use the extras:

```bash
pip install -e "adapters/copilot_vectorstore/[azure]"
```

### Development Installation

```bash
pip install -e "adapters/copilot_vectorstore/[dev]"
pip install faiss-cpu numpy qdrant-client azure-search-documents azure-identity
```

## Quick Start

### Using the Factory (Recommended)

```python
from copilot_vectorstore import create_vector_store

from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_Faiss,
    DriverConfig_VectorStore_Inmemory,
)

# For testing
store = create_vector_store(
    AdapterConfig_VectorStore(
        vector_store_type="inmemory",
        driver=DriverConfig_VectorStore_Inmemory(),
    )
)

# FAISS example
store = create_vector_store(
    AdapterConfig_VectorStore(
        vector_store_type="faiss",
        driver=DriverConfig_VectorStore_Faiss(dimension=768, index_type="flat"),
    )
)
```

### Direct Instantiation

```python
from copilot_vectorstore import InMemoryVectorStore, FAISSVectorStore

# In-memory store
store = InMemoryVectorStore()

# FAISS store
store = FAISSVectorStore(dimension=384, index_type="flat")
```

### Basic Operations

```python
# Add single embedding
store.add_embedding(
    id="doc1",
    vector=[0.1, 0.2, 0.3, ...],
    metadata={"text": "Hello world", "source": "email"}
)

# Add multiple embeddings (batch)
store.add_embeddings(
    ids=["doc2", "doc3", "doc4"],
    vectors=[[...], [...], [...]],
    metadatas=[{...}, {...}, {...}]
)

# Query for similar vectors
results = store.query(
    query_vector=[0.15, 0.25, 0.35, ...],
    top_k=5
)

for result in results:
    print(f"ID: {result.id}, Score: {result.score}")
    print(f"Metadata: {result.metadata}")

# Get specific embedding
result = store.get("doc1")

# Delete embedding
store.delete("doc1")

# Get count
print(f"Total embeddings: {store.count()}")

# Clear all embeddings
store.clear()
```

## Configuration

### Environment Variables

- `VECTOR_STORE_TYPE`: Vector store type (`inmemory`, `faiss`, `qdrant`, `azure_ai_search`)
    - Used by the schema-driven config loader (not read directly by `create_vector_store`).

#### Qdrant Configuration

- `QDRANT_HOST`: Qdrant server host (default: `vectorstore`)
- `QDRANT_PORT`: Qdrant server port (default: `6333`)
- `QDRANT_API_KEY`: Optional API key for authentication
- `QDRANT_COLLECTION`: Collection name (default: `embeddings`)
- `QDRANT_DISTANCE`: Distance metric - `cosine` or `euclid` (default: `cosine`)
- `QDRANT_UPSERT_BATCH_SIZE`: Batch size for upsert operations (default: `100`)

#### Azure AI Search Configuration

- `AZURE_SEARCH_ENDPOINT`: Azure AI Search service endpoint
- `AZURE_SEARCH_API_KEY`: Azure AI Search API key (not required if using managed identity)
- `AZURE_SEARCH_INDEX_NAME`: Name of the search index (default: `embeddings`)

### Backend-Specific Options

#### FAISS

```python
from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_Faiss,
)
from copilot_vectorstore import create_vector_store

store = create_vector_store(
    AdapterConfig_VectorStore(
        vector_store_type="faiss",
        driver=DriverConfig_VectorStore_Faiss(
            dimension=384,
            index_type="flat",  # or "ivf" for large datasets
            persist_path="/path/to/index.faiss",  # optional
        ),
    )
)
```

#### Qdrant

```python
# Local Qdrant instance
from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_Qdrant,
)
from copilot_vectorstore import create_vector_store

store = create_vector_store(
    AdapterConfig_VectorStore(
        vector_store_type="qdrant",
        driver=DriverConfig_VectorStore_Qdrant(
            host="localhost",
            port=6333,
            collection_name="embeddings",
            vector_size=384,
            distance="cosine",  # or "euclidean" (alias: "euclid")
            upsert_batch_size=100,
        ),
    )
)

# Qdrant Cloud with API key
store = create_vector_store(
    AdapterConfig_VectorStore(
        vector_store_type="qdrant",
        driver=DriverConfig_VectorStore_Qdrant(
            host="your-cluster.cloud.qdrant.io",
            port=6333,
            api_key="your-api-key",
            collection_name="production_embeddings",
            vector_size=768,
            distance="cosine",
            upsert_batch_size=100,
        ),
    )
)
```

#### Azure AI Search

```python
# Using API key authentication
from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_AzureAiSearch,
)
from copilot_vectorstore import create_vector_store

store = create_vector_store(
    AdapterConfig_VectorStore(
        vector_store_type="azure_ai_search",
        driver=DriverConfig_VectorStore_AzureAiSearch(
            endpoint="https://your-service.search.windows.net",
            api_key="your-api-key",
            index_name="embeddings",
            vector_size=384,
        ),
    )
)

# Using managed identity (Azure VM, Azure Functions, etc.)
store = create_vector_store(
    AdapterConfig_VectorStore(
        vector_store_type="azure_ai_search",
        driver=DriverConfig_VectorStore_AzureAiSearch(
            endpoint="https://your-service.search.windows.net",
            use_managed_identity=True,
            index_name="production_embeddings",
            vector_size=768,
        ),
    )
)
```

### Azure AI Search Configuration

#### Environment Variables

- `AZURE_SEARCH_ENDPOINT`: Azure AI Search service endpoint (e.g., `https://myservice.search.windows.net`)
- `AZURE_SEARCH_API_KEY`: Azure AI Search API key (not required if using managed identity)
- `AZURE_SEARCH_INDEX_NAME`: Name of the search index (default: `embeddings`)

#### Example with Environment Variables

```python
import os
from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_AzureAiSearch,
)
from copilot_vectorstore import create_vector_store

os.environ["AZURE_SEARCH_ENDPOINT"] = "https://myservice.search.windows.net"
os.environ["AZURE_SEARCH_API_KEY"] = "your-api-key"
os.environ["AZURE_SEARCH_INDEX_NAME"] = "my_embeddings"

store = create_vector_store(
    AdapterConfig_VectorStore(
        vector_store_type="azure_ai_search",
        driver=DriverConfig_VectorStore_AzureAiSearch(
            endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
            api_key=os.environ["AZURE_SEARCH_API_KEY"],
            index_name=os.environ["AZURE_SEARCH_INDEX_NAME"],
            vector_size=384,
        ),
    )
)
```

#### Managed Identity Authentication

When running on Azure (VM, App Service, Functions, AKS), you can use managed identity:

```python
store = create_vector_store(
    AdapterConfig_VectorStore(
        vector_store_type="azure_ai_search",
        driver=DriverConfig_VectorStore_AzureAiSearch(
            endpoint="https://your-service.search.windows.net",
            index_name="embeddings",
            vector_size=384,
            use_managed_identity=True,
        ),
    )
)
```

**Prerequisites:**
- Enable managed identity for your Azure resource
- Grant the identity "Search Index Data Contributor" and "Search Service Contributor" roles on the Azure AI Search service

#### Index Configuration

The Azure AI Search adapter automatically creates an index with the following configuration:

- **Vector Algorithm**: HNSW (Hierarchical Navigable Small World) for efficient similarity search
- **Distance Metric**: Cosine similarity
- **Vector Field**: `embedding` field with configurable dimensions
- **Metadata Field**: JSON-serialized metadata for filtering and retrieval

The index is created automatically on first use if it doesn't exist. If the index exists, the adapter validates that the vector dimensions match.

## Architecture

### VectorStore Interface

All backends implement the `VectorStore` abstract base class:

```python
class VectorStore(ABC):
    @abstractmethod
    def add_embedding(self, id: str, vector: List[float], metadata: Dict[str, Any]) -> None

    @abstractmethod
    def add_embeddings(self, ids: List[str], vectors: List[List[float]],
                      metadatas: List[Dict[str, Any]]) -> None

    @abstractmethod
    def query(self, query_vector: List[float], top_k: int = 10) -> List[SearchResult]

    @abstractmethod
    def delete(self, id: str) -> None

    @abstractmethod
    def clear(self) -> None

    @abstractmethod
    def count(self) -> int

    @abstractmethod
    def get(self, id: str) -> SearchResult
```

### SearchResult

Query results are returned as `SearchResult` objects:

```python
@dataclass
class SearchResult:
    id: str                    # Document/chunk ID
    score: float               # Similarity score (higher = more similar)
    vector: List[float]        # The embedding vector
    metadata: Dict[str, Any]   # Associated metadata
```

## Integration with Services

### Embedding Service

```python
from copilot_vectorstore import create_vector_store
from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_Inmemory,
)

class EmbeddingService:
    def __init__(self):
        self.vector_store = create_vector_store(
            AdapterConfig_VectorStore(
                vector_store_type="inmemory",
                driver=DriverConfig_VectorStore_Inmemory(),
            )
        )

    def store_embeddings(self, chunks, embeddings):
        self.vector_store.add_embeddings(
            ids=[chunk.id for chunk in chunks],
            vectors=embeddings,
            metadatas=[chunk.metadata for chunk in chunks]
        )
```

### Summarization Service

```python
from copilot_vectorstore import create_vector_store
from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_Inmemory,
)

class SummarizationService:
    def __init__(self):
        self.vector_store = create_vector_store(
            AdapterConfig_VectorStore(
                vector_store_type="inmemory",
                driver=DriverConfig_VectorStore_Inmemory(),
            )
        )

    def get_relevant_context(self, query_embedding, top_k=10):
        results = self.vector_store.query(
            query_vector=query_embedding,
            top_k=top_k
        )
        return [r.metadata for r in results]
```

## Testing

The module includes comprehensive tests for all implementations:

```bash
# Run all tests
cd adapters/copilot_vectorstore
pytest tests/

# Run specific test file
pytest tests/test_inmemory.py

# Run with coverage
pytest tests/ --cov=copilot_vectorstore --cov-report=html
```

## Contributing

### Adding a New Backend

1. Create a new file `adapters/copilot_vectorstore/your_backend.py`
2. Implement the `VectorStore` interface
3. Add to `factory.py` and `__init__.py`
4. Write comprehensive tests in `adapters/copilot_vectorstore/tests/test_your_backend.py`
5. Update this README

Example skeleton:

```python
from .interface import VectorStore, SearchResult
from typing import List, Dict, Any

class YourBackendVectorStore(VectorStore):
    def __init__(self, **config):
        # Initialize your backend
        pass

    def add_embedding(self, id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        # Implementation
        pass

    # ... implement all abstract methods
```

## Performance Considerations

### InMemoryVectorStore
- **Best for**: Testing, small datasets (<10k vectors)
- **Complexity**: O(n) for queries
- **Memory**: All vectors stored in RAM

### FAISSVectorStore
- **Best for**: Production, large datasets (10k+ vectors)
- **Complexity**: O(log n) to O(1) depending on index type
- **Memory**: Vectors stored in RAM, can save/load from disk
- **Index types**:
  - `flat`: Exact search, slower but accurate
  - `ivf`: Approximate search, faster for large datasets

### QdrantVectorStore
- **Best for**: Production, persistent storage, distributed deployments
- **Complexity**: O(log n) with HNSW indexing
- **Persistence**: Automatic persistence to disk
- **Features**:
  - Built-in filtering on metadata
  - Horizontal scaling support
  - Cloud-hosted or self-hosted options
  - HNSW (Hierarchical Navigable Small World) algorithm for fast approximate search

## Troubleshooting

### Qdrant Connection Issues

**Problem**: `ConnectionError: Failed to connect to Qdrant`

**Solutions**:
- Verify Qdrant server is running: `curl http://localhost:6333/health`
- Check `QDRANT_HOST` and `QDRANT_PORT` environment variables
- Ensure firewall allows connection to Qdrant port
- For Qdrant Cloud, verify API key is correct

**Problem**: `ValueError: Collection 'X' exists with different vector size`

**Solutions**:
- Delete the existing collection or use a different collection name
- Ensure `dimension` parameter matches the existing collection's vector size

**Problem**: `ImportError: qdrant-client is not installed`

**Solution**:
```bash
pip install qdrant-client
```

### Running Qdrant Locally

Using Docker:
```bash
docker run -p 6333:6333 qdrant/qdrant
```

Using Docker Compose:
```yaml
services:
  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
    volumes:
      - ./qdrant_storage:/qdrant/storage
```

## License

MIT License - See LICENSE file for details
