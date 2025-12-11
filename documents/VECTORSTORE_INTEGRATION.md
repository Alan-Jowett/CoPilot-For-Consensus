<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Vector Store Integration Guide

This guide explains how to integrate the vector store abstraction layer into your Copilot-for-Consensus services.

## Overview

The vector store abstraction provides a unified interface for storing and querying embedding vectors across different backends (FAISS, in-memory, Qdrant, Azure Cognitive Search).

## Installation

### Basic Installation (InMemory only)

```bash
cd adapters/copilot_vectorstore
pip install -e .
```

### With FAISS Support (Recommended for Production)

```bash
cd adapters/copilot_vectorstore
pip install -e .
pip install faiss-cpu  # or faiss-gpu for GPU acceleration
```

## Quick Start

### 1. Using the Factory Pattern (Recommended)

```python
from copilot_vectorstore import create_vector_store

# Create store based on environment variable VECTOR_STORE_BACKEND
store = create_vector_store(dimension=384)

# Or specify backend explicitly
store = create_vector_store(backend="faiss", dimension=768)
```

### 2. Storing Embeddings

```python
# Add a single embedding
store.add_embedding(
    id="chunk-001",
    vector=[0.1, 0.2, 0.3, ...],  # 384-dimensional vector
    metadata={
        "message_id": "msg-123",
        "text": "Original text content",
        "thread_id": "thread-456"
    }
)

# Add multiple embeddings (more efficient)
store.add_embeddings(
    ids=["chunk-001", "chunk-002", "chunk-003"],
    vectors=[vector1, vector2, vector3],
    metadatas=[metadata1, metadata2, metadata3]
)
```

### 3. Querying for Similar Vectors

```python
# Query for top-k similar vectors
results = store.query(
    query_vector=[0.15, 0.25, 0.35, ...],
    top_k=10
)

for result in results:
    print(f"ID: {result.id}")
    print(f"Score: {result.score}")  # Higher = more similar
    print(f"Metadata: {result.metadata}")
    print(f"Vector: {result.vector[:5]}...")  # First 5 dimensions
```

## Service Integration Examples

### Embedding Service Integration

```python
from copilot_vectorstore import create_vector_store

class EmbeddingService:
    def __init__(self):
        # Use environment variable to select backend
        self.vector_store = create_vector_store(dimension=384)
        self.embedding_model = load_embedding_model()
    
    def process_chunks(self, chunks):
        """Process and store chunk embeddings."""
        # Generate embeddings
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedding_model.encode(texts)
        
        # Store in vector store
        ids = [chunk["chunk_id"] for chunk in chunks]
        metadatas = [
            {
                "message_id": chunk["message_id"],
                "text": chunk["text"],
                "thread_id": chunk["thread_id"],
            }
            for chunk in chunks
        ]
        
        self.vector_store.add_embeddings(ids, embeddings, metadatas)
        print(f"Stored {len(chunks)} embeddings")
```

### Summarization Service Integration

```python
from copilot_vectorstore import create_vector_store

class SummarizationService:
    def __init__(self):
        self.vector_store = create_vector_store(dimension=384)
        self.embedding_model = load_embedding_model()
        self.llm = load_llm()
    
    def summarize_thread(self, thread_query):
        """Generate summary using retrieved context."""
        # Embed the query
        query_embedding = self.embedding_model.encode([thread_query])[0]
        
        # Retrieve relevant chunks
        results = self.vector_store.query(
            query_vector=query_embedding,
            top_k=10
        )
        
        # Build context for LLM
        context = "\n\n".join([
            f"[{i+1}] {r.metadata['text']}"
            for i, r in enumerate(results)
        ])
        
        # Generate summary
        prompt = f"Context:\n{context}\n\nSummarize the discussion:"
        summary = self.llm.generate(prompt)
        
        return summary, results
```

## Configuration

### Environment Variables

Set these environment variables to configure the vector store:

```bash
# Backend selection
export VECTOR_STORE_BACKEND=faiss  # Options: inmemory, faiss, qdrant, azure

# For FAISS backend
export FAISS_INDEX_TYPE=flat  # Options: flat, ivf
export FAISS_PERSIST_PATH=/data/faiss/index.bin  # Optional: persist to disk
```

### Backend-Specific Configuration

#### In-Memory (for testing)

```python
from copilot_vectorstore import InMemoryVectorStore

store = InMemoryVectorStore()
# Simple, no additional configuration needed
```

#### FAISS (for production)

```python
from copilot_vectorstore import FAISSVectorStore

# Flat index (exact search, slower but accurate)
store = FAISSVectorStore(
    dimension=384,
    index_type="flat"
)

# IVF index (approximate search, faster for large datasets)
store = FAISSVectorStore(
    dimension=384,
    index_type="ivf",
    persist_path="/data/faiss/index.bin"
)

# Save index to disk
store.save()

# Load index from disk
store.load()
```

## RAG (Retrieval-Augmented Generation) Pattern

```python
from copilot_vectorstore import create_vector_store

class RAGSystem:
    def __init__(self):
        self.vector_store = create_vector_store(dimension=384)
        self.embedding_model = load_embedding_model()
        self.llm = load_llm()
    
    def index_documents(self, documents):
        """Index documents for retrieval."""
        texts = [doc["text"] for doc in documents]
        embeddings = self.embedding_model.encode(texts)
        
        ids = [doc["id"] for doc in documents]
        metadatas = documents
        
        self.vector_store.add_embeddings(ids, embeddings, metadatas)
    
    def ask(self, question, top_k=5):
        """Answer a question using retrieved context."""
        # Embed question
        question_embedding = self.embedding_model.encode([question])[0]
        
        # Retrieve relevant documents
        results = self.vector_store.query(question_embedding, top_k=top_k)
        
        # Build context
        context = "\n\n".join([
            f"Document {r.id}: {r.metadata['text']}"
            for r in results
        ])
        
        # Generate answer
        prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
        answer = self.llm.generate(prompt)
        
        return answer, results
```

## Testing

### Using In-Memory Store for Tests

```python
import pytest
from copilot_vectorstore import InMemoryVectorStore

def test_embedding_service():
    # Use in-memory store for testing
    store = InMemoryVectorStore()
    
    # Add test data
    store.add_embedding(
        id="test-1",
        vector=[1.0, 0.0, 0.0],
        metadata={"text": "test"}
    )
    
    # Query
    results = store.query([0.9, 0.1, 0.0], top_k=1)
    
    assert len(results) == 1
    assert results[0].id == "test-1"
```

## Performance Considerations

### In-Memory Store
- **Best for**: Testing, small datasets (<10k vectors)
- **Query Complexity**: O(n)
- **Memory**: All vectors in RAM

### FAISS Store
- **Best for**: Production, large datasets (10k+ vectors)
- **Query Complexity**: O(log n) to O(1) depending on index type
- **Memory**: Vectors in RAM, can persist to disk
- **Flat Index**: Exact search, O(n) but optimized
- **IVF Index**: Approximate search, O(log n), suitable for millions of vectors

### Choosing the Right Backend

```python
# Development/Testing
VECTOR_STORE_BACKEND=inmemory

# Small-Medium Production (<100k vectors)
VECTOR_STORE_BACKEND=faiss
FAISS_INDEX_TYPE=flat

# Large Production (>100k vectors)
VECTOR_STORE_BACKEND=faiss
FAISS_INDEX_TYPE=ivf

# Cloud/Distributed (future)
VECTOR_STORE_BACKEND=qdrant
VECTOR_STORE_BACKEND=azure
```

## Troubleshooting

### FAISS Not Installed

```bash
# Error: ImportError: FAISS is not installed
pip install faiss-cpu
# or for GPU support
pip install faiss-gpu
```

### Dimension Mismatch

```python
# Error: ValueError: Vector dimension (512) doesn't match index dimension (384)
# Solution: Ensure all vectors have the same dimension
store = create_vector_store(dimension=512)  # Match your embedding model
```

### Out of Memory

```python
# For large datasets, use IVF index instead of flat
store = FAISSVectorStore(dimension=384, index_type="ivf")

# Or consider using Qdrant/Azure for distributed storage
store = create_vector_store(backend="qdrant", dimension=384)
```

## Next Steps

1. **For Embedding Service**: See `adapters/copilot_vectorstore/examples.py` for complete examples
2. **For Summarization Service**: Integrate query functionality for retrieval
3. **For Production**: Configure FAISS with persistence and appropriate index type
4. **For Scale**: Consider migrating to Qdrant or Azure Cognitive Search

## Contributing

To add support for a new backend:

1. Create a new file `adapters/copilot_vectorstore/your_backend.py`
2. Implement the `VectorStore` interface
3. Add to `factory.py` and `__init__.py`
4. Write tests in `adapters/copilot_vectorstore/tests/test_your_backend.py`
5. Update documentation

See `adapters/copilot_vectorstore/README.md` for detailed contribution guidelines.
