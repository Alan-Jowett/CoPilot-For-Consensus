# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example integration patterns for embedding and summarization services."""

from typing import List, Dict, Any
from copilot_vectorstore import create_vector_store


class EmbeddingServiceExample:
    """Example integration with the Embedding Service.

    This demonstrates how to use the vector store abstraction to store
    embeddings generated from text chunks.
    """

    def __init__(self, embedding_dimension: int = 384):
        """Initialize the embedding service with a vector store.

        Args:
            embedding_dimension: Dimension of the embedding vectors
                                (default: 384 for all-MiniLM-L6-v2)
        """
        # Use factory to create vector store based on environment config
        self.vector_store = create_vector_store(dimension=embedding_dimension)
        self.embedding_dimension = embedding_dimension

    def process_chunks(self, chunks: List[Dict[str, Any]],
                      embeddings: List[List[float]]) -> None:
        """Store chunk embeddings in the vector store.

        Args:
            chunks: List of chunk metadata dictionaries containing:
                   - chunk_id: Unique identifier
                   - message_id: Source message ID
                   - text: The chunk text
                   - thread_id: Thread identifier
                   - timestamp: When the chunk was created
            embeddings: List of embedding vectors corresponding to chunks
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")

        # Extract IDs and prepare metadata
        ids = [chunk["chunk_id"] for chunk in chunks]
        metadatas = [
            {
                "message_id": chunk["message_id"],
                "text": chunk["text"],
                "thread_id": chunk.get("thread_id"),
                "timestamp": chunk.get("timestamp"),
            }
            for chunk in chunks
        ]

        # Store in batch for better performance
        self.vector_store.add_embeddings(ids, embeddings, metadatas)
        print(f"Stored {len(chunks)} embeddings in vector store")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored embeddings.

        Returns:
            Dictionary with embedding statistics
        """
        return {
            "total_embeddings": self.vector_store.count(),
            "embedding_dimension": self.embedding_dimension,
        }


class SummarizationServiceExample:
    """Example integration with the Summarization Service.

    This demonstrates how to query the vector store to retrieve relevant
    context for summarization.
    """

    def __init__(self, embedding_dimension: int = 384):
        """Initialize the summarization service with a vector store.

        Args:
            embedding_dimension: Dimension of the embedding vectors
        """
        self.vector_store = create_vector_store(dimension=embedding_dimension)

    def get_relevant_context(self, query_embedding: List[float],
                            top_k: int = 10) -> List[Dict[str, Any]]:
        """Retrieve the most relevant text chunks for a query.

        Args:
            query_embedding: The query embedding vector
            top_k: Number of top results to retrieve

        Returns:
            List of dictionaries containing chunk text and metadata
        """
        results = self.vector_store.query(query_embedding, top_k=top_k)

        # Format results for summarization
        context_chunks = []
        for result in results:
            context_chunks.append({
                "chunk_id": result.id,
                "text": result.metadata.get("text", ""),
                "message_id": result.metadata.get("message_id"),
                "thread_id": result.metadata.get("thread_id"),
                "similarity_score": result.score,
            })

        return context_chunks

    def build_prompt_with_context(self, query: str,
                                  query_embedding: List[float],
                                  top_k: int = 10) -> str:
        """Build a summarization prompt with retrieved context.

        Args:
            query: The summarization query
            query_embedding: The query embedding vector
            top_k: Number of context chunks to retrieve

        Returns:
            Formatted prompt string with context
        """
        context_chunks = self.get_relevant_context(query_embedding, top_k)

        # Build prompt with context
        prompt = f"Query: {query}\n\n"
        prompt += "Relevant Context:\n"

        for i, chunk in enumerate(context_chunks, 1):
            prompt += f"\n[{i}] (similarity: {chunk['similarity_score']:.3f})\n"
            prompt += f"{chunk['text']}\n"

        prompt += "\nBased on the above context, please provide a summary.\n"

        return prompt


class SimpleRAGExample:
    """Example of a simple Retrieval-Augmented Generation (RAG) pattern.

    This combines embedding storage and retrieval for question answering.
    """

    def __init__(self, embedding_dimension: int = 384):
        """Initialize the RAG system.

        Args:
            embedding_dimension: Dimension of the embedding vectors
        """
        self.vector_store = create_vector_store(dimension=embedding_dimension)
        self.embedding_dimension = embedding_dimension

    def index_documents(self, documents: List[Dict[str, Any]],
                       embeddings: List[List[float]]) -> None:
        """Index documents with their embeddings.

        Args:
            documents: List of documents with 'id', 'text', and metadata
            embeddings: Corresponding embedding vectors
        """
        ids = [doc["id"] for doc in documents]
        metadatas = [
            {k: v for k, v in doc.items() if k != "id"}
            for doc in documents
        ]

        self.vector_store.add_embeddings(ids, embeddings, metadatas)

    def search(self, query_embedding: List[float],
              top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant documents.

        Args:
            query_embedding: The query embedding vector
            top_k: Number of results to return

        Returns:
            List of relevant documents with similarity scores
        """
        results = self.vector_store.query(query_embedding, top_k)

        return [
            {
                "id": r.id,
                "score": r.score,
                **r.metadata
            }
            for r in results
        ]

    def clear_index(self) -> None:
        """Clear all indexed documents."""
        self.vector_store.clear()


def example_usage():
    """Demonstrate basic usage of the vector store with services."""
    print("=== Vector Store Integration Examples ===\n")

    # Example 1: Embedding Service
    print("1. Embedding Service Integration")
    print("-" * 50)
    embedding_service = EmbeddingServiceExample(embedding_dimension=384)

    # Simulate some chunks and embeddings
    chunks = [
        {
            "chunk_id": "chunk-1",
            "message_id": "msg-001",
            "text": "This is the first chunk of text",
            "thread_id": "thread-1",
        },
        {
            "chunk_id": "chunk-2",
            "message_id": "msg-002",
            "text": "This is the second chunk of text",
            "thread_id": "thread-1",
        },
    ]
    # In real usage, these would come from an embedding model
    embeddings = [
        [0.1] * 384,  # Placeholder embedding
        [0.2] * 384,  # Placeholder embedding
    ]

    embedding_service.process_chunks(chunks, embeddings)
    print(f"Stats: {embedding_service.get_stats()}\n")

    # Example 2: Summarization Service
    print("2. Summarization Service Integration")
    print("-" * 50)
    summarization_service = SummarizationServiceExample(embedding_dimension=384)
    summarization_service.vector_store = embedding_service.vector_store  # Share the store

    query_embedding = [0.15] * 384  # Placeholder query embedding
    context = summarization_service.get_relevant_context(query_embedding, top_k=2)
    print(f"Retrieved {len(context)} relevant chunks")
    for ctx in context:
        print(f"  - Chunk {ctx['chunk_id']}: score={ctx['similarity_score']:.3f}")
    print()

    # Example 3: RAG Pattern
    print("3. Simple RAG Pattern")
    print("-" * 50)
    rag = SimpleRAGExample(embedding_dimension=384)

    documents = [
        {"id": "doc1", "text": "Python is a programming language", "category": "tech"},
        {"id": "doc2", "text": "Machine learning uses neural networks", "category": "AI"},
    ]
    doc_embeddings = [[0.3] * 384, [0.4] * 384]

    rag.index_documents(documents, doc_embeddings)

    query_emb = [0.35] * 384
    results = rag.search(query_emb, top_k=2)
    print(f"Search results: {len(results)} documents")
    for result in results:
        print(f"  - {result['id']}: {result['text']} (score: {result['score']:.3f})")


if __name__ == "__main__":
    example_usage()
