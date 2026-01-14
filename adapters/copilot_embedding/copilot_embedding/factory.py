# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating embedding providers."""

import logging
from typing import Union

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


EmbeddingBackendDriverConfig = Union[
    DriverConfig_EmbeddingBackend_AzureOpenai,
    DriverConfig_EmbeddingBackend_Huggingface,
    DriverConfig_EmbeddingBackend_Mock,
    DriverConfig_EmbeddingBackend_Openai,
    DriverConfig_EmbeddingBackend_Sentencetransformers,
]


def create_embedding_provider(
    driver_name: str | AdapterConfig_EmbeddingBackend,
    driver_config: EmbeddingBackendDriverConfig | None = None,
) -> EmbeddingProvider:
    """Create an embedding provider from configuration.

    Args:
        driver_name:
            Backend type (required) or an adapter config object.
            Options: 'mock', 'sentencetransformers', 'openai', 'azure', 'azure_openai', 'huggingface'
        driver_config: Driver configuration for the selected backend.

    Returns:
        EmbeddingProvider instance

    Raises:
        ValueError: If driver_name is unknown or required configuration is missing
    """
    if isinstance(driver_name, AdapterConfig_EmbeddingBackend):
        adapter_config = driver_name
        backend = str(adapter_config.embedding_backend_type).lower()
        config = adapter_config.driver
    else:
        if not driver_name:
            raise ValueError(
                "driver_name parameter is required. "
                "Must be one of: mock, sentencetransformers, openai, azure, azure_openai, huggingface"
            )

        backend = str(driver_name).lower()
        config = driver_config

    if backend == "azure":
        backend = "azure_openai"

    if config is None:
        raise ValueError(
            "driver_name parameter is required. "
            "Must be one of: mock, sentencetransformers, openai, azure, azure_openai, huggingface"
        )

    logger.info(f"Creating embedding provider with backend: {backend}")

    if backend == "mock":
        return MockEmbeddingProvider.from_config(config)

    if backend == "sentencetransformers":
        return SentenceTransformerEmbeddingProvider.from_config(config)

    if backend == "openai":
        return OpenAIEmbeddingProvider.from_config(config, driver_name="openai")

    if backend == "azure_openai":
        return OpenAIEmbeddingProvider.from_config(config, driver_name="azure_openai")

    if backend == "huggingface":
        return HuggingFaceEmbeddingProvider.from_config(config)

    raise ValueError(
        f"Unknown embedding backend driver: {backend}. "
        f"Supported backends: mock, sentencetransformers, openai, azure_openai, huggingface"
    )
