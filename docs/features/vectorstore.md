<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Vector Store Integration

Integration guide for the vector store abstraction layer supporting multiple backends (FAISS, Qdrant, Azure Cognitive Search).

## Overview

Unified interface for storing and querying embedding vectors across different backends with factory pattern and automatic backend selection via environment variables.

## Installation

**FAISS only** (recommended for production):
```bash
cd adapters/copilot_vectorstore
pip install -e .
pip install faiss-cpu  # or faiss-gpu for GPU
```

## Quick Start

**Factory pattern** (environment variable based):
```python
from copilot_vectorstore import create_vector_store

store = create_vector_store(dimension=384)  # Reads VECTOR_STORE_BACKEND env var
# or explicit: create_vector_store(backend="faiss", dimension=768)
```

**Store embeddings**:
```python
# Single embedding
store.add_embedding(
    id="chunk-001",
    vector=[0.1, 0.2, 0.3, ...],
    metadata={"message_id": "msg-123", "text": "...", "thread_id": "..."}
)

# Batch operation
store.add_embeddings(ids=[...], vectors=[...], metadata=[...])
```

**Search**:
```python
results = store.search(query_vector, top_k=10, threshold=0.5)
for result in results:
    print(f"ID: {result.id}, Score: {result.score}, Metadata: {result.metadata}")
```

## Supported Backends

| Backend | Environment Variable | Status | Scaling | Use Case |
|---------|----------------------|--------|---------|----------|
| **FAISS** | `VECTOR_STORE_BACKEND=faiss` | ✅ Stable | Single-machine (100M+ vectors) | Default, offline, development |
| **Qdrant** | `VECTOR_STORE_BACKEND=qdrant` | ✅ Stable | Distributed, cloud-ready | Production, multi-instance |
| **Azure Cognitive Search** | `VECTOR_STORE_BACKEND=azure` | ✅ Stable | Azure-managed | Enterprise Azure deployments |
| **In-Memory** | `VECTOR_STORE_BACKEND=memory` | ⚠️ Limited | None (single instance) | Testing, demo |

## Configuration Examples

**.env for local development** (FAISS):
```
VECTOR_STORE_BACKEND=faiss
VECTOR_STORE_DIMENSION=384
FAISS_INDEX_PATH=/data/vector_index.faiss
```

**.env for Qdrant**:
```
VECTOR_STORE_BACKEND=qdrant
QDRANT_HOST=vectorstore
QDRANT_PORT=6333
QDRANT_COLLECTION=embeddings
```

**.env for Azure**:
```
VECTOR_STORE_BACKEND=azure
AZURE_SEARCH_ENDPOINT=https://<name>.search.windows.net
AZURE_SEARCH_KEY=<key>
AZURE_SEARCH_INDEX=embeddings
```

## Using in Services

The embedding and orchestrator services use the factory to select backends automatically:
```python
# In embedding service
from copilot_vectorstore import create_vector_store

store = create_vector_store(dimension=384)
store.add_embedding(chunk_id, embedding_vector, metadata)
```

For detailed API reference and advanced usage, see the [adapter README](../../adapters/copilot_vectorstore/README.md).
