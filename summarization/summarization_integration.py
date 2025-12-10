# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example integration of chunking abstraction with summarization service."""

import logging
from typing import List, Dict, Any

# Import from the SDK
from copilot_events.chunkers import Chunk


logger = logging.getLogger(__name__)


class SummarizationService:
    """Summarization service that can work with chunked content.
    
    This example shows how the summarization service can consume chunks
    produced by different chunking strategies and use them for RAG-based
    summarization without needing to know the specific strategy used.
    """
    
    def __init__(self, llm_backend: str = "ollama", llm_model: str = "mistral"):
        """Initialize the summarization service.
        
        Args:
            llm_backend: LLM backend to use (ollama, azure, openai)
            llm_model: Model name
        """
        self.llm_backend = llm_backend
        self.llm_model = llm_model
        logger.info(
            f"Initialized SummarizationService with {llm_backend}/{llm_model}"
        )
    
    def summarize_chunks(
        self,
        chunks: List[Chunk],
        top_k: int = 12
    ) -> Dict[str, Any]:
        """Summarize a thread based on retrieved chunks.
        
        The summarization service doesn't need to know which chunking
        strategy was used - it simply works with the Chunk objects.
        
        Args:
            chunks: List of relevant chunks to summarize (e.g., from vector search)
            top_k: Number of top chunks to use in summary
            
        Returns:
            Summary dictionary with text and metadata
        """
        # In a real implementation, this would:
        # 1. Retrieve top-k most relevant chunks from vector store
        # 2. Build a prompt with chunk context
        # 3. Call LLM to generate summary
        # 4. Extract citations from chunks
        
        # For this example, we just create a mock summary
        selected_chunks = chunks[:top_k] if len(chunks) > top_k else chunks
        
        # Build context from chunks
        context = "\n\n".join(
            f"[Chunk {chunk.chunk_index}] {chunk.text[:200]}..."
            for chunk in selected_chunks
        )
        
        summary = {
            "summary_text": self._generate_mock_summary(selected_chunks),
            "chunks_used": len(selected_chunks),
            "chunk_ids": [chunk.chunk_id for chunk in selected_chunks],
            "citations": self._extract_citations(selected_chunks),
            "llm_backend": self.llm_backend,
            "llm_model": self.llm_model,
        }
        
        logger.info(
            f"Generated summary using {len(selected_chunks)} chunks "
            f"with {len(summary['citations'])} citations"
        )
        
        return summary
    
    def _generate_mock_summary(self, chunks: List[Chunk]) -> str:
        """Generate a mock summary.
        
        In a real implementation, this would call the LLM.
        
        Args:
            chunks: Chunks to summarize
            
        Returns:
            Summary text
        """
        return (
            f"This thread discusses {len(chunks)} main topics. "
            f"The conversation involves contributions from multiple participants "
            f"and covers technical details about the subject matter."
        )
    
    def _extract_citations(self, chunks: List[Chunk]) -> List[Dict[str, Any]]:
        """Extract citations from chunks.
        
        Args:
            chunks: Chunks to cite
            
        Returns:
            List of citation objects
        """
        citations = []
        for i, chunk in enumerate(chunks):
            citation = {
                "citation_id": i + 1,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "sender": chunk.metadata.get("sender", "unknown"),
                "date": chunk.metadata.get("date", "unknown"),
                "text_preview": chunk.text[:100] + "..." if len(chunk.text) > 100 else chunk.text,
            }
            citations.append(citation)
        return citations
    
    def estimate_context_window(self, chunks: List[Chunk]) -> Dict[str, Any]:
        """Estimate token usage for context window.
        
        Different chunking strategies may produce different token distributions,
        but the summarization service handles them uniformly.
        
        Args:
            chunks: Chunks to analyze
            
        Returns:
            Dictionary with token estimates
        """
        total_tokens = sum(chunk.token_count for chunk in chunks)
        avg_tokens = total_tokens / len(chunks) if chunks else 0
        
        return {
            "total_tokens": total_tokens,
            "average_tokens_per_chunk": avg_tokens,
            "chunk_count": len(chunks),
            "estimated_context_usage": min(total_tokens, 3000),  # Typical context limit
        }


def example_summarization_workflow():
    """Example of summarization workflow with different chunking strategies."""
    import os
    import sys
    
    # Add chunking directory to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'chunking'))
    
    summarization_service = SummarizationService()
    
    # Example 1: Summarize chunks from TokenWindowChunker
    print("=== Example 1: Summarizing TokenWindow Chunks ===")
    os.environ["CHUNKING_STRATEGY"] = "token_window"
    os.environ["CHUNK_SIZE_TOKENS"] = "200"
    
    from chunking_service import ChunkingService
    
    chunking_service = ChunkingService()
    
    message_text = """
    The proposed approach for connection migration addresses the key security
    concerns raised in previous discussions. We should proceed with implementing
    the validation process as outlined in section 3.2.
    
    I agree with Alice's points about the handshake protocol, but I think we
    need additional clarification on the timeout handling. The current draft
    doesn't specify what happens when the validation fails.
    
    Bob raised an important question about backward compatibility. We need to
    ensure that older clients can still connect even if they don't support
    the new migration features.
    """ * 3
    
    chunks = chunking_service.chunk_message(
        message_id="<msg1@example.com>",
        text=message_text,
        metadata={
            "sender": "discussion@example.com",
            "date": "2023-10-15T12:00:00Z",
            "subject": "Connection Migration Discussion"
        }
    )
    
    summary = summarization_service.summarize_chunks(chunks, top_k=5)
    print(f"Summary: {summary['summary_text']}")
    print(f"Used {summary['chunks_used']} chunks with {len(summary['citations'])} citations\n")
    
    # Example 2: Summarize chunks from FixedSizeChunker
    print("=== Example 2: Summarizing FixedSize Chunks ===")
    os.environ["CHUNKING_STRATEGY"] = "fixed_size"
    os.environ["MESSAGES_PER_CHUNK"] = "2"
    
    chunking_service = ChunkingService()
    
    thread_messages = [
        {
            "message_id": "<msg1@example.com>",
            "text": "Initial proposal for the new feature. Here's what I suggest..."
        },
        {
            "message_id": "<msg2@example.com>",
            "text": "I support the proposal with some modifications to section 2..."
        },
        {
            "message_id": "<msg3@example.com>",
            "text": "I have concerns about the performance implications..."
        },
        {
            "message_id": "<msg4@example.com>",
            "text": "Let me address the performance concerns. We've done testing..."
        },
        {
            "message_id": "<msg5@example.com>",
            "text": "Based on the discussion, I think we should proceed with..."
        },
    ]
    
    chunks = chunking_service.chunk_thread(
        thread_id="<thread1@example.com>",
        messages=thread_messages,
        metadata={
            "subject": "New Feature Proposal",
            "start_date": "2023-10-15T10:00:00Z"
        }
    )
    
    context_estimate = summarization_service.estimate_context_window(chunks)
    print(f"Context window estimate: {context_estimate['total_tokens']} tokens")
    print(f"Average tokens per chunk: {context_estimate['average_tokens_per_chunk']:.1f}")
    
    summary = summarization_service.summarize_chunks(chunks)
    print(f"Summary: {summary['summary_text']}\n")
    
    # Example 3: Summarize chunks from SemanticChunker
    print("=== Example 3: Summarizing Semantic Chunks ===")
    os.environ["CHUNKING_STRATEGY"] = "semantic"
    os.environ["CHUNK_SIZE_TOKENS"] = "300"
    
    chunking_service = ChunkingService()
    
    semantic_text = """
    The technical working group has been discussing the new protocol extension.
    There are three main concerns that need to be addressed. First, we need to
    ensure backward compatibility. Second, the performance impact must be minimal.
    Third, security implications need thorough review.
    
    Several members have proposed solutions. Alice suggested a phased rollout
    approach. Bob recommended additional validation checks. Carol pointed out
    potential edge cases in the current design.
    
    After careful consideration, the group reached consensus on the following
    approach. We will implement the core features first. Additional enhancements
    will be added in subsequent iterations. Testing will be comprehensive.
    """
    
    chunks = chunking_service.chunk_message(
        message_id="<msg6@example.com>",
        text=semantic_text,
        metadata={
            "sender": "chair@example.com",
            "date": "2023-10-15T15:00:00Z",
            "subject": "Working Group Summary"
        }
    )
    
    summary = summarization_service.summarize_chunks(chunks)
    print(f"Summary: {summary['summary_text']}")
    print(f"Citations: {len(summary['citations'])}\n")
    
    print("=== Key Takeaway ===")
    print("The summarization service works seamlessly with all chunking strategies")
    print("because it depends on the Chunk abstraction, not specific implementations.")
    print("Different strategies may produce different chunk distributions, but the")
    print("summarization logic remains the same.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    example_summarization_workflow()
