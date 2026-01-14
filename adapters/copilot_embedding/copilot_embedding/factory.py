# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating embedding providers."""

import logging

from copilot_config.generated.adapters.embedding_backend import (
    AdapterConfig_EmbeddingBackend,
)

from .base import EmbeddingProvider
from .huggingface_provider import HuggingFaceEmbeddingProvider
from .mock_provider import MockEmbeddingProvider
from .openai_provider import OpenAIEmbeddingProvider
from .sentence_transformer_provider import SentenceTransformerEmbeddingProvider

logger = logging.getLogger(__name__)


def create_embedding_provider(
    config: AdapterConfig_EmbeddingBackend,
) -> EmbeddingProvider:
    """Create an embedding provider from configuration.

    Args:
        config: Typed adapter configuration for embedding_backend.

    Returns:
        EmbeddingProvider instance

    Raises:
        ValueError: If config is missing or embedding_backend_type is not recognized
    """
    if config is None:
        raise ValueError("embedding_backend config is required")

    backend = str(config.embedding_backend_type).lower()
    driver_config = config.driver

    logger.info(f"Creating embedding provider with backend: {backend}")

    if backend == "mock":
        return MockEmbeddingProvider.from_config(driver_config)

    if backend == "sentencetransformers":
        return SentenceTransformerEmbeddingProvider.from_config(driver_config)

    if backend == "openai":
        return OpenAIEmbeddingProvider.from_config(driver_config, driver_name="openai")

    if backend == "azure_openai":
        return OpenAIEmbeddingProvider.from_config(driver_config, driver_name="azure_openai")

    if backend == "huggingface":
        return HuggingFaceEmbeddingProvider.from_config(driver_config)

    raise ValueError(
        f"Unknown embedding backend driver: {backend}. "
        f"Supported backends: mock, sentencetransformers, openai, azure_openai, huggingface"
    )
