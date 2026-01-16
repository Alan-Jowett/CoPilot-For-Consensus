# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Embedding Adapter.

A shared library for embedding generation with support for multiple backends
including OpenAI, Azure OpenAI, local models, and test mocks.

This module provides an abstraction layer for embedding providers that allows
plugging in different backends without changing downstream logic.

Example:
    >>> from copilot_embedding import create_embedding_provider
    >>> from copilot_config.generated.adapters.embedding_backend import (
    ...     AdapterConfig_EmbeddingBackend,
    ...     DriverConfig_EmbeddingBackend_Mock,
    ... )
    >>>
    >>> # Create a mock provider for testing
    >>> provider = create_embedding_provider(
    ...     AdapterConfig_EmbeddingBackend(
    ...         embedding_backend_type="mock",
    ...         driver=DriverConfig_EmbeddingBackend_Mock(dimension=128),
    ...     )
    ... )
    >>> embedding = provider.embed("Your text here")
    >>>
    >>> embedding = provider.embed("Test text")
    >>> assert len(embedding) == 128
"""

__version__ = "0.1.0"

from .base import EmbeddingProvider
from .factory import create_embedding_provider

__all__ = [
    # Version
    "__version__",
    # Core interface
    "EmbeddingProvider",
    # Factory
    "create_embedding_provider",
]
