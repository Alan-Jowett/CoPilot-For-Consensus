# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating summarizer instances based on configuration."""

import os
import logging
from typing import Optional
try:
    from summarizer import Summarizer
    from openai_summarizer import OpenAISummarizer, DEFAULT_AZURE_API_VERSION
    from mock_summarizer import MockSummarizer
    from local_llm_summarizer import LocalLLMSummarizer
    from llamacpp_summarizer import LlamaCppSummarizer
except ImportError:
    from .summarizer import Summarizer
    from .openai_summarizer import OpenAISummarizer, DEFAULT_AZURE_API_VERSION
    from .mock_summarizer import MockSummarizer
    from .local_llm_summarizer import LocalLLMSummarizer
    from .llamacpp_summarizer import LlamaCppSummarizer

logger = logging.getLogger(__name__)

class SummarizerFactory:
    """Factory for creating summarizer instances.
    
    Creates the appropriate summarizer based on configuration or
    environment variables.
    """
    
    @staticmethod
    def create_summarizer(
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ) -> Summarizer:
        """Create a summarizer instance based on provider type.
        
        Args:
            provider: Provider type (required). Options: "openai", "azure", "local", "llamacpp", "mock"
            model: Model name to use. Required for openai, azure, local, and llamacpp backends.
            api_key: API key for cloud providers. Required for openai and azure.
            base_url: Base URL for Azure, local, or llamacpp endpoints. Required for azure, local, and llamacpp.
            
        Returns:
            Summarizer instance
            
        Raises:
            ValueError: If provider is unknown or required config is missing
        """
        if not provider:
            raise ValueError(
                "provider parameter is required. "
                "Must be one of: openai, azure, local, llamacpp, mock"
            )
        
        provider = provider.lower()
        
        logger.info("Creating summarizer with provider: %s", provider)
        
        if provider == "openai":
            if not api_key:
                raise ValueError(
                    "api_key parameter is required for OpenAI provider. "
                    "Provide the API key explicitly"
                )
            
            if not model:
                raise ValueError(
                    "model parameter is required for OpenAI provider. "
                    "Specify a model name (e.g., 'gpt-3.5-turbo', 'gpt-4')"
                )
            
            return OpenAISummarizer(
                api_key=api_key,
                model=model,
                base_url=base_url
            )
            
        elif provider == "azure":
            if not api_key:
                raise ValueError(
                    "api_key parameter is required for Azure provider. "
                    "Provide the Azure OpenAI API key explicitly"
                )
            
            if not base_url:
                raise ValueError(
                    "base_url parameter is required for Azure provider. "
                    "Provide the Azure OpenAI endpoint explicitly"
                )
            
            if not model:
                raise ValueError(
                    "model parameter is required for Azure provider. "
                    "Specify a model name (e.g., 'gpt-3.5-turbo', 'gpt-4')"
                )
            
            # Extract Azure-specific parameters
            api_version = kwargs.get("api_version", DEFAULT_AZURE_API_VERSION)
            deployment_name = kwargs.get("deployment_name")
            
            return OpenAISummarizer(
                api_key=api_key,
                model=model,
                base_url=base_url,
                api_version=api_version,
                deployment_name=deployment_name
            )
            
        elif provider == "local":
            if not model:
                raise ValueError(
                    "model parameter is required for local LLM provider. "
                    "Specify a model name (e.g., 'mistral', 'llama2')"
                )
            
            if not base_url:
                raise ValueError(
                    "base_url parameter is required for local LLM provider. "
                    "Specify the local LLM endpoint (e.g., 'http://localhost:11434')"
                )
            
            return LocalLLMSummarizer(
                model=model,
                base_url=base_url
            )
            
        elif provider == "llamacpp":
            if not model:
                raise ValueError(
                    "model parameter is required for llamacpp provider. "
                    "Specify a model name (e.g., 'mistral-7b-instruct-v0.2.Q4_K_M')"
                )
            
            if not base_url:
                raise ValueError(
                    "base_url parameter is required for llamacpp provider. "
                    "Specify the llama.cpp server endpoint (e.g., 'http://localhost:8080')"
                )
            
            return LlamaCppSummarizer(
                model=model,
                base_url=base_url
            )
            
        elif provider == "mock":
            # MockSummarizer has its own default for latency_ms in the class
            # Pass it only if explicitly provided
            if "latency_ms" in kwargs:
                return MockSummarizer(latency_ms=kwargs["latency_ms"])
            else:
                return MockSummarizer()
            
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported providers: openai, azure, local, llamacpp, mock"
            )
