# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""OpenAI and Azure OpenAI embedding provider."""

import importlib
import logging

from typing import Any, Literal

from copilot_config.generated.adapters.embedding_backend import (
    DriverConfig_EmbeddingBackend_AzureOpenai,
    DriverConfig_EmbeddingBackend_Openai,
)

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI/Azure OpenAI embedding provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-ada-002",
        api_base: str | None = None,
        api_version: str | None = None,
        deployment_name: str | None = None
    ):
        """Initialize OpenAI embedding provider.

        Args:
            api_key: OpenAI or Azure OpenAI API key
            model: Model name (for OpenAI) or deployment name (for Azure)
            api_base: API base URL (for Azure OpenAI)
            api_version: API version (for Azure OpenAI)
            deployment_name: Deployment name (for Azure OpenAI)
        """
        try:
            openai_module = importlib.import_module("openai")
        except ImportError as exc:
            raise ImportError(
                "openai is required for OpenAIEmbeddingProvider. "
                "Install it with: pip install openai"
            ) from exc

        # Access client classes dynamically so Pyright does not require the optional
        # dependency (CI gate runs without installing every ML/LLM provider).
        OpenAI: Any = getattr(openai_module, "OpenAI", None)
        AzureOpenAI: Any = getattr(openai_module, "AzureOpenAI", None)
        if OpenAI is None or AzureOpenAI is None:
            raise ImportError(
                "openai is installed but missing expected client classes "
                "(OpenAI/AzureOpenAI). Please upgrade: pip install --upgrade openai"
            )

        self.model = model
        self.is_azure = api_base is not None

        if api_base is not None:
            logger.info(f"Initializing Azure OpenAI embedding provider with deployment: {deployment_name or model}")
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version or "2023-05-15",
                azure_endpoint=api_base
            )
            self.deployment_name = deployment_name or model
        else:
            logger.info(f"Initializing OpenAI embedding provider with model: {model}")
            self.client = OpenAI(api_key=api_key)

    @classmethod
    def from_config(
        cls,
        driver_config: DriverConfig_EmbeddingBackend_Openai | DriverConfig_EmbeddingBackend_AzureOpenai,
        *,
        driver_name: Literal["openai", "azure_openai"],
    ):
        """Create provider from configuration.

        Supports both OpenAI and Azure OpenAI backends. Uses Azure mode if api_base is provided.

        Args:
            driver_config: Config object containing (attribute or dict-style):
                           - api_key: API key (required)
                           - model: Model name (required for OpenAI)
                           - api_base: API endpoint (required for Azure)
                           - api_version: API version (optional, for Azure)
                           - deployment_name: Deployment name (optional, for Azure)

        Returns:
            Configured OpenAIEmbeddingProvider

        """
        if driver_name == "azure_openai":
            if not isinstance(driver_config, DriverConfig_EmbeddingBackend_AzureOpenai):
                raise TypeError("driver_config must be DriverConfig_EmbeddingBackend_AzureOpenai")

            return cls(
                api_key=str(driver_config.api_key),
                model=str(driver_config.model) if driver_config.model else str(driver_config.deployment_name),
                api_base=str(driver_config.api_base),
                api_version=driver_config.api_version,
                deployment_name=driver_config.deployment_name,
            )

        if not isinstance(driver_config, DriverConfig_EmbeddingBackend_Openai):
            raise TypeError("driver_config must be DriverConfig_EmbeddingBackend_Openai")

        return cls(api_key=str(driver_config.api_key), model=str(driver_config.model))

    def embed(self, text: str) -> list[float]:
        """Generate embeddings using OpenAI API.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If text is None, non-string, or empty
        """
        if not text.strip():
            raise ValueError("Text cannot be empty or whitespace-only")

        if self.is_azure:
            response = self.client.embeddings.create(
                input=text,
                model=self.deployment_name
            )
        else:
            response = self.client.embeddings.create(
                input=text,
                model=self.model
            )

        return response.data[0].embedding
