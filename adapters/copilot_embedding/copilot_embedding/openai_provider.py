# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""OpenAI and Azure OpenAI embedding provider."""

import logging

from copilot_config import DriverConfig

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
            from openai import AzureOpenAI, OpenAI
        except ImportError:
            raise ImportError(
                "openai is required for OpenAIEmbeddingProvider. "
                "Install it with: pip install openai"
            )

        self.model = model
        self.is_azure = api_base is not None

        if self.is_azure:
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
    def from_config(cls, driver_config: DriverConfig):
        """Create provider from a DriverConfig.
        
        Supports both OpenAI and Azure OpenAI backends. Uses Azure mode if api_base is provided.
        
        Args:
            driver_config: DriverConfig containing:
                           - api_key: API key (required)
                           - model: Model name (required for OpenAI)
                           - api_base: API endpoint (required for Azure)
                           - api_version: API version (optional, for Azure)
                           - deployment_name: Deployment name (optional, for Azure)
        
        Returns:
            Configured OpenAIEmbeddingProvider
        
        Raises:
            ValueError: If required attributes are missing
            TypeError: If driver_config is not a DriverConfig instance
        """
        driver_name = (driver_config.driver_name or "").lower()

        api_key = driver_config.api_key
        model = driver_config.model
        api_base = driver_config.config.get("api_base")
        api_version = driver_config.config.get("api_version")
        deployment_name = driver_config.config.get("deployment_name")

        if not api_key:
            raise ValueError(
                "api_key parameter is required for OpenAI/Azure backend. "
                "Provide the API key explicitly"
            )

        # Azure backend detection: if driver_name is azure_openai or api_base provided
        if driver_name == "azure_openai" or api_base:
            if not api_base:
                raise ValueError("api_base parameter is required for Azure OpenAI backend")
            if not model and not deployment_name:
                raise ValueError(
                    "Either model or deployment_name parameter is required for Azure backend. "
                    "Specify the model or deployment name"
                )
            model = model or deployment_name
            return cls(
                api_key=str(api_key),
                model=str(model),
                api_base=str(api_base),
                api_version=api_version,
                deployment_name=deployment_name,
            )

        if driver_name and driver_name != "openai":
            raise ValueError(f"Unsupported driver_name for OpenAI provider: {driver_name}")

        if not model:
            raise ValueError(
                "model parameter is required for OpenAI backend. "
                "Specify a model name (e.g., 'text-embedding-ada-002')"
            )
        return cls(api_key=str(api_key), model=str(model))

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
