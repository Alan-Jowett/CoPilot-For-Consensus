# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating embedding providers."""

import logging

from copilot_config.generated.adapters.embedding_backend import (
    AdapterConfig_EmbeddingBackend,
    DriverConfig_EmbeddingBackend_AzureOpenai,
    DriverConfig_EmbeddingBackend_Huggingface,
    DriverConfig_EmbeddingBackend_Mock,
    DriverConfig_EmbeddingBackend_Openai,
    DriverConfig_EmbeddingBackend_Sentencetransformers,
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
        if not isinstance(driver_config, DriverConfig_EmbeddingBackend_Mock):
            raise TypeError("driver_config must be DriverConfig_EmbeddingBackend_Mock")
        return MockEmbeddingProvider.from_config(driver_config)

    if backend == "sentencetransformers":
        if not isinstance(driver_config, DriverConfig_EmbeddingBackend_Sentencetransformers):
            raise TypeError("driver_config must be DriverConfig_EmbeddingBackend_Sentencetransformers")
        return SentenceTransformerEmbeddingProvider.from_config(driver_config)

    if backend == "openai":
        if not isinstance(driver_config, DriverConfig_EmbeddingBackend_Openai):
            raise TypeError("driver_config must be DriverConfig_EmbeddingBackend_Openai")
        return OpenAIEmbeddingProvider.from_config(driver_config, driver_name="openai")

    if backend == "azure_openai":
        if not isinstance(driver_config, DriverConfig_EmbeddingBackend_AzureOpenai):
            raise TypeError("driver_config must be DriverConfig_EmbeddingBackend_AzureOpenai")
        return OpenAIEmbeddingProvider.from_config(driver_config, driver_name="azure_openai")

    if backend == "huggingface":
        if not isinstance(driver_config, DriverConfig_EmbeddingBackend_Huggingface):
            raise TypeError("driver_config must be DriverConfig_EmbeddingBackend_Huggingface")
        return HuggingFaceEmbeddingProvider.from_config(driver_config)

    raise ValueError(
        f"Unknown embedding backend driver: {backend}. "
        f"Supported backends: mock, sentencetransformers, openai, azure_openai, huggingface"
    )
