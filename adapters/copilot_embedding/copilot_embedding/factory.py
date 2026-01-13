# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating embedding providers (DriverConfig-based)."""

import logging
from copilot_config import DriverConfig

from .base import EmbeddingProvider
from .huggingface_provider import HuggingFaceEmbeddingProvider
from .mock_provider import MockEmbeddingProvider
from .openai_provider import OpenAIEmbeddingProvider
from .sentence_transformer_provider import SentenceTransformerEmbeddingProvider

logger = logging.getLogger(__name__)


def create_embedding_provider(
    driver_name: str,
    driver_config: DriverConfig
) -> EmbeddingProvider:
    """Create an embedding provider from configuration.

    Args:
        driver_name: Backend type (required).
                Options: 'mock', 'sentencetransformers', 'openai', 'azure', 'azure_openai', 'huggingface'
        driver_config: Configuration object with attributes for the selected backend

    Returns:
        EmbeddingProvider instance

    Raises:
        ValueError: If driver_name is unknown or required configuration is missing
    """
    if not driver_name:
        raise ValueError(
            "driver_name parameter is required. "
            "Must be one of: mock, sentencetransformers, openai, azure, azure_openai, huggingface"
        )

    backend = str(driver_name).lower()
    logger.info(f"Creating embedding provider with backend: {backend}")

    if backend == "mock":
        return MockEmbeddingProvider.from_config(driver_config)

    if backend == "sentencetransformers":
        return SentenceTransformerEmbeddingProvider.from_config(driver_config)

    if backend == "openai":
        return OpenAIEmbeddingProvider.from_config(driver_config)

    if backend in {"azure", "azure_openai"}:
        return OpenAIEmbeddingProvider.from_config(driver_config)

    if backend == "huggingface":
        return HuggingFaceEmbeddingProvider.from_config(driver_config)

    raise ValueError(
        f"Unknown embedding backend driver: {driver_name}. "
        f"Supported backends: mock, sentencetransformers, openai, azure, azure_openai, huggingface"
    )
