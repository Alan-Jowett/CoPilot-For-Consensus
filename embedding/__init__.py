# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Embedding service package."""

from .providers import (
    EmbeddingProvider,
    MockEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    OpenAIEmbeddingProvider,
    HuggingFaceEmbeddingProvider,
)
from .factory import create_embedding_provider

__all__ = [
    "EmbeddingProvider",
    "MockEmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "HuggingFaceEmbeddingProvider",
    "create_embedding_provider",
]
