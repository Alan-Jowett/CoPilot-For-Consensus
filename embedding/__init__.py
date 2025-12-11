# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Embedding service package.

This module re-exports the embedding provider SDK for convenience.
The actual implementation is in the copilot_embedding SDK module.
"""

# Re-export from copilot_embedding SDK
try:
    from copilot_embedding import (
        EmbeddingProvider,
        MockEmbeddingProvider,
        SentenceTransformerEmbeddingProvider,
        OpenAIEmbeddingProvider,
        HuggingFaceEmbeddingProvider,
        create_embedding_provider,
    )

    __all__ = [
        "EmbeddingProvider",
        "MockEmbeddingProvider",
        "SentenceTransformerEmbeddingProvider",
        "OpenAIEmbeddingProvider",
        "HuggingFaceEmbeddingProvider",
        "create_embedding_provider",
    ]
except ImportError:
    # SDK not installed yet
    pass

