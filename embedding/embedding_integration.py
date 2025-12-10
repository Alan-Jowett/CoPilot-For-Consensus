# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example integration of chunking abstraction with embedding service."""

import logging
from typing import List, Dict, Any

# Import from the SDK
from copilot_events.chunkers import Chunk, create_chunker


logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding service that can work with chunked content.
    
    This example shows how the embedding service can consume chunks
    produced by different chunking strategies without needing to know
    the specific strategy used.
    """
    
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        """Initialize the embedding service.
        
        Args:
            embedding_model: Name of the embedding model to use
        """
        self.embedding_model = embedding_model
        logger.info(f"Initialized EmbeddingService with model: {embedding_model}")
    
    def generate_embeddings(self, chunks: List[Chunk]) -> List[Dict[str, Any]]:
        """Generate embeddings for a list of chunks.
        
        The embedding service doesn't need to know which chunking strategy
        was used - it simply processes the Chunk objects it receives.
        
        Args:
            chunks: List of chunks to embed
            
        Returns:
            List of embedding objects with vectors and metadata
        """
        embeddings = []
        
        for chunk in chunks:
            # In a real implementation, this would call the actual embedding model
            # For this example, we just create a placeholder
            embedding = {
                "chunk_id": chunk.chunk_id,
                "vector": self._generate_mock_embedding(chunk.text),
                "metadata": {
                    **chunk.metadata,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                    "embedding_model": self.embedding_model,
                }
            }
            embeddings.append(embedding)
        
        logger.info(f"Generated embeddings for {len(chunks)} chunks")
        return embeddings
    
    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Generate a mock embedding vector.
        
        In a real implementation, this would use sentence-transformers,
        Azure OpenAI, or another embedding backend.
        
        Args:
            text: Text to embed
            
        Returns:
            Mock embedding vector
        """
        # Return a simple mock vector
        return [0.0] * 384  # 384 dimensions for all-MiniLM-L6-v2


def example_embedding_workflow():
    """Example of embedding workflow with different chunking strategies."""
    import os
    import sys
    
    # Add chunking directory to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'chunking'))
    
    # Example: Use TokenWindowChunker
    print("=== Example 1: TokenWindowChunker ===")
    os.environ["CHUNKING_STRATEGY"] = "token_window"
    os.environ["CHUNK_SIZE_TOKENS"] = "200"
    
    from chunking_service import ChunkingService
    
    chunking_service = ChunkingService()
    embedding_service = EmbeddingService()
    
    message_text = """
    This is an example email message with substantial content that will
    be chunked using the token window strategy. The chunker will break
    this into smaller pieces based on the configured token size.
    
    The token window chunker uses a sliding window approach with overlap
    to ensure context is preserved across chunk boundaries.
    """ * 5  # Repeat to make it longer
    
    chunks = chunking_service.chunk_message(
        message_id="<msg1@example.com>",
        text=message_text,
        metadata={"sender": "test@example.com"}
    )
    
    embeddings = embedding_service.generate_embeddings(chunks)
    print(f"Generated {len(embeddings)} embeddings using TokenWindowChunker\n")
    
    # Example: Use FixedSizeChunker
    print("=== Example 2: FixedSizeChunker ===")
    os.environ["CHUNKING_STRATEGY"] = "fixed_size"
    os.environ["MESSAGES_PER_CHUNK"] = "3"
    
    # Recreate service with new config
    chunking_service = ChunkingService()
    
    thread_messages = [
        {"message_id": f"<msg{i}@example.com>", "text": f"Message {i} content"}
        for i in range(10)
    ]
    
    chunks = chunking_service.chunk_thread(
        thread_id="<thread1@example.com>",
        messages=thread_messages,
        metadata={"subject": "Test Thread"}
    )
    
    embeddings = embedding_service.generate_embeddings(chunks)
    print(f"Generated {len(embeddings)} embeddings using FixedSizeChunker\n")
    
    # Example: Use SemanticChunker
    print("=== Example 3: SemanticChunker ===")
    os.environ["CHUNKING_STRATEGY"] = "semantic"
    os.environ["CHUNK_SIZE_TOKENS"] = "300"
    
    chunking_service = ChunkingService()
    
    semantic_text = """
    First sentence of the message. Second sentence continues the thought.
    Third sentence adds more detail. Fourth sentence concludes the paragraph.
    
    New paragraph starts here. This paragraph discusses a different topic.
    It has its own sentences. They form a coherent unit.
    
    Final paragraph wraps up the message. It provides a conclusion.
    """
    
    chunks = chunking_service.chunk_message(
        message_id="<msg2@example.com>",
        text=semantic_text,
        metadata={"sender": "semantic@example.com"}
    )
    
    embeddings = embedding_service.generate_embeddings(chunks)
    print(f"Generated {len(embeddings)} embeddings using SemanticChunker\n")
    
    print("=== Key Takeaway ===")
    print("The embedding service works seamlessly with all chunking strategies")
    print("because it depends on the Chunk abstraction, not specific implementations.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    example_embedding_workflow()
