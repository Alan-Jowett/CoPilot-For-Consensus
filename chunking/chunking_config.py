# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Configuration for chunking service."""

import os
from typing import Optional


class ChunkingConfig:
    """Configuration for the chunking service.
    
    Attributes:
        chunking_strategy: Strategy to use for chunking (token_window, fixed_size, semantic)
        chunk_size: Target chunk size in tokens
        overlap: Overlap between chunks in tokens
        messages_per_chunk: Number of messages per chunk (for fixed_size strategy)
        min_chunk_size: Minimum chunk size in tokens
        max_chunk_size: Maximum chunk size in tokens
    """
    
    def __init__(self):
        """Initialize chunking configuration from environment variables."""
        self.chunking_strategy = os.getenv("CHUNKING_STRATEGY", "token_window")
        self.chunk_size = int(os.getenv("CHUNK_SIZE_TOKENS", "384"))
        self.overlap = int(os.getenv("CHUNK_OVERLAP_TOKENS", "50"))
        self.messages_per_chunk = int(os.getenv("MESSAGES_PER_CHUNK", "5"))
        self.min_chunk_size = int(os.getenv("MIN_CHUNK_SIZE_TOKENS", "100"))
        self.max_chunk_size = int(os.getenv("MAX_CHUNK_SIZE_TOKENS", "512"))
    
    def get_chunker_params(self) -> dict:
        """Get parameters for creating a chunker based on strategy.
        
        Returns:
            Dictionary of parameters for the chunker factory
        """
        params = {
            "strategy": self.chunking_strategy,
        }
        
        if self.chunking_strategy == "token_window":
            params.update({
                "chunk_size": self.chunk_size,
                "overlap": self.overlap,
                "min_chunk_size": self.min_chunk_size,
                "max_chunk_size": self.max_chunk_size,
            })
        elif self.chunking_strategy == "fixed_size":
            params["messages_per_chunk"] = self.messages_per_chunk
        elif self.chunking_strategy == "semantic":
            params["chunk_size"] = self.chunk_size
        
        return params
