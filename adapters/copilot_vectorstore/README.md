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
  - `AzureVectorStore`: (Planned) Azure Cognitive Search integration
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

### Development Installation

```bash
pip install -e "adapters/copilot_vectorstore/[dev]"
pip install faiss-cpu numpy qdrant-client
```

## Quick Start

### Using the Factory (Recommended)

```python
from copilot_vectorstore import create_vector_store

# Create using environment variable VECTOR_STORE_BACKEND
store = create_vector_store(dimension=384)

# Or explicitly specify backend
store = create_vector_store(backend="faiss", dimension=768)

# For testing
store = create_vector_store(backend="inmemory")
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

- `VECTOR_STORE_BACKEND`: Backend to use (`inmemory`, `faiss`, `qdrant`, `azure`)
  - Default: `faiss`

#### Qdrant Configuration

- `QDRANT_HOST`: Qdrant server host (default: `localhost`)
- `QDRANT_PORT`: Qdrant server port (default: `6333`)
- `QDRANT_API_KEY`: Optional API key for authentication
- `QDRANT_COLLECTION`: Collection name (default: `embeddings`)
- `QDRANT_DISTANCE`: Distance metric - `cosine` or `euclid` (default: `cosine`)
- `QDRANT_BATCH_SIZE`: Batch size for upsert operations (default: `100`)

### Backend-Specific Options

#### FAISS

```python
store = create_vector_store(
    backend="faiss",
    dimension=384,
    index_type="flat",  # or "ivf" for large datasets
    persist_path="/path/to/index.faiss"  # optional
)
```

#### Qdrant

```python
# Local Qdrant instance
store = create_vector_store(
    backend="qdrant",
    dimension=384,
    host="localhost",
    port=6333,
    collection_name="embeddings",
    distance="cosine",  # or "euclid"
)

# Qdrant Cloud with API key
store = create_vector_store(
    backend="qdrant",
    dimension=768,
    host="your-cluster.cloud.qdrant.io",
    port=6333,
    api_key="your-api-key",
    collection_name="production_embeddings",
)

# Using environment variables
os.environ["QDRANT_HOST"] = "qdrant.example.com"
os.environ["QDRANT_PORT"] = "6333"
os.environ["QDRANT_API_KEY"] = "secret"
os.environ["QDRANT_COLLECTION"] = "my_collection"
store = create_vector_store(backend="qdrant", dimension=384)
```

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

class EmbeddingService:
    def __init__(self):
        self.vector_store = create_vector_store(dimension=384)
    
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

class SummarizationService:
    def __init__(self):
        self.vector_store = create_vector_store(dimension=384)
    
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
