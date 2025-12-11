# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Chunking service implementation using the thread chunking abstraction."""

import logging
from typing import List, Dict, Any

# Import from the SDK
from copilot_chunking import (
    ThreadChunker,
    Thread,
    Chunk,
    create_chunker,
)

from chunking_config import ChunkingConfig


logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for chunking email threads using pluggable strategies.
    
    This service uses the ThreadChunker abstraction layer to support
    different chunking strategies for breaking up email threads before
    embedding or summarization.
    """
    
    def __init__(self, config: ChunkingConfig = None):
        """Initialize the chunking service.
        
        Args:
            config: Chunking configuration (uses default if not provided)
        """
        self.config = config or ChunkingConfig()
        self.chunker = self._create_chunker()
        logger.info(
            f"Initialized ChunkingService with strategy: {self.config.chunking_strategy}"
        )
    
    def _create_chunker(self) -> ThreadChunker:
        """Create a chunker based on configuration.
        
        Returns:
            ThreadChunker instance
        """
        params = self.config.get_chunker_params()
        return create_chunker(**params)
    
    def chunk_message(
        self,
        message_id: str,
        text: str,
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """Chunk a single message.
        
        Args:
            message_id: Unique identifier for the message
            text: Message text to chunk
            metadata: Message metadata (sender, date, subject, etc.)
            
        Returns:
            List of chunks
            
        Raises:
            ValueError: If text is empty or invalid
        """
        thread = Thread(
            thread_id=message_id,
            text=text,
            metadata=metadata
        )
        
        try:
            chunks = self.chunker.chunk(thread)
            logger.info(
                f"Chunked message {message_id} into {len(chunks)} chunks "
                f"using {self.config.chunking_strategy} strategy"
            )
            return chunks
        except Exception as e:
            logger.error(f"Failed to chunk message {message_id}: {e}")
            raise
    
    def chunk_thread(
        self,
        thread_id: str,
        messages: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """Chunk an entire thread.
        
        Args:
            thread_id: Unique identifier for the thread
            messages: List of message dictionaries with 'text' or 'body' field
            metadata: Thread-level metadata
            
        Returns:
            List of chunks
            
        Raises:
            ValueError: If messages is empty or invalid
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")
        
        # Combine all message texts
        combined_text = "\n\n".join(
            msg.get("text", msg.get("body", ""))
            for msg in messages
        )
        
        thread = Thread(
            thread_id=thread_id,
            text=combined_text,
            metadata=metadata,
            messages=messages
        )
        
        try:
            chunks = self.chunker.chunk(thread)
            logger.info(
                f"Chunked thread {thread_id} ({len(messages)} messages) "
                f"into {len(chunks)} chunks using {self.config.chunking_strategy} strategy"
            )
            return chunks
        except Exception as e:
            logger.error(f"Failed to chunk thread {thread_id}: {e}")
            raise
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get information about the current chunking strategy.
        
        Returns:
            Dictionary with strategy information
        """
        return {
            "strategy": self.config.chunking_strategy,
            "chunk_size": self.config.chunk_size,
            "overlap": self.config.overlap,
            "messages_per_chunk": self.config.messages_per_chunk,
            "min_chunk_size": self.config.min_chunk_size,
            "max_chunk_size": self.config.max_chunk_size,
        }


def example_usage():
    """Example of how to use the ChunkingService."""
    # Create service with default configuration (reads from env vars)
    service = ChunkingService()
    
    # Example: Chunk a single message
    message_metadata = {
        "sender": "alice@example.com",
        "sender_name": "Alice Developer",
        "date": "2023-10-15T12:34:56Z",
        "subject": "Re: QUIC connection migration concerns"
    }
    
    message_text = """
    I agree with the proposed approach for connection migration.
    
    The current draft addresses most of the security concerns that were
    raised in the previous discussion. However, I think we should add
    more detail about the validation process.
    
    In particular, section 3.2 should clarify what happens when...
    """
    
    try:
        chunks = service.chunk_message(
            message_id="<msg123@example.com>",
            text=message_text,
            metadata=message_metadata
        )
        
        for chunk in chunks:
            print(f"Chunk {chunk.chunk_index}: {chunk.token_count} tokens")
            print(f"  Text: {chunk.text[:100]}...")
            print()
    
    except Exception as e:
        logger.error(f"Chunking failed: {e}")
    
    # Example: Chunk a thread with multiple messages
    thread_messages = [
        {
            "message_id": "<msg1@example.com>",
            "text": "Initial message in the thread...",
        },
        {
            "message_id": "<msg2@example.com>",
            "text": "Reply to the initial message...",
        },
        {
            "message_id": "<msg3@example.com>",
            "text": "Follow-up discussion...",
        },
    ]
    
    thread_metadata = {
        "subject": "Thread Subject",
        "start_date": "2023-10-15T10:00:00Z",
    }
    
    try:
        chunks = service.chunk_thread(
            thread_id="<thread123@example.com>",
            messages=thread_messages,
            metadata=thread_metadata
        )
        
        print(f"Thread chunked into {len(chunks)} chunks")
    
    except Exception as e:
        logger.error(f"Thread chunking failed: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    example_usage()
