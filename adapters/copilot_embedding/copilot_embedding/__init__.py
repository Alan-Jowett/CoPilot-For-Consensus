# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Embedding Adapter.

A shared library for embedding generation with support for multiple backends
including OpenAI, Azure OpenAI, local models, and test mocks.

This module provides an abstraction layer for embedding providers that allows
plugging in different backends without changing downstream logic.

Example:
    >>> from copilot_embedding import create_embedding_provider
    >>>
    >>> # Create a provider with environment-based configuration
    >>> provider = create_embedding_provider()
    >>> embedding = provider.embed("Your text here")
    >>>
    >>> # Create a mock provider for testing
    >>> test_provider = create_embedding_provider(backend="mock", dimension=128)
    >>> embedding = test_provider.embed("Test text")
    >>> assert len(embedding) == 128
"""

__version__ = "0.1.0"

from .providers import (
    EmbeddingProvider,
    MockEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    OpenAIEmbeddingProvider,
    HuggingFaceEmbeddingProvider,
)
from .factory import create_embedding_provider

__all__ = [
    # Version
    "__version__",
    # Core interface
    "EmbeddingProvider",
    # Implementations
    "MockEmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "HuggingFaceEmbeddingProvider",
    # Factory
    "create_embedding_provider",
]
