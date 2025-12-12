# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating summarizer instances based on configuration."""

import os
import logging
from typing import Optional
try:
    from summarizer import Summarizer
    from openai_summarizer import OpenAISummarizer
    from mock_summarizer import MockSummarizer
    from local_llm_summarizer import LocalLLMSummarizer
except ImportError:
    from .summarizer import Summarizer
    from .openai_summarizer import OpenAISummarizer
    from .mock_summarizer import MockSummarizer
    from .local_llm_summarizer import LocalLLMSummarizer

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
        base_url: Optional[str] = None
    ) -> Summarizer:
        """Create a summarizer instance based on provider type.
        
        Args:
            provider: Provider type ("openai", "azure", "local", "mock")
                     If None, reads from SUMMARIZER_PROVIDER env var
            model: Model name to use. If None, uses provider default
            api_key: API key for cloud providers. If None, reads from env
            base_url: Base URL for Azure or local endpoints
            
        Returns:
            Summarizer instance
            
        Raises:
            ValueError: If provider is unknown or required config is missing
        """
        # Read from environment if not provided
        if provider is None:
            provider = os.getenv("SUMMARIZER_PROVIDER", "mock")
        
        provider = provider.lower()
        
        logger.info("Creating summarizer with provider: %s", provider)
        
        if provider == "openai":
            if api_key is None:
                api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")
            
            if model is None:
                model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            
            return OpenAISummarizer(
                api_key=api_key,
                model=model,
                base_url=base_url
            )
            
        elif provider == "azure":
            if api_key is None:
                api_key = os.getenv("AZURE_OPENAI_API_KEY")
            if not api_key:
                raise ValueError("Azure OpenAI API key required. Set AZURE_OPENAI_API_KEY environment variable.")
            
            if base_url is None:
                base_url = os.getenv("AZURE_OPENAI_ENDPOINT")
            if not base_url:
                raise ValueError("Azure OpenAI endpoint required. Set AZURE_OPENAI_ENDPOINT environment variable.")
            
            if model is None:
                model = os.getenv("AZURE_OPENAI_MODEL", "gpt-3.5-turbo")
            
            return OpenAISummarizer(
                api_key=api_key,
                model=model,
                base_url=base_url
            )
            
        elif provider == "local":
            if model is None:
                model = os.getenv("LOCAL_LLM_MODEL", "mistral")
            
            if base_url is None:
                base_url = os.getenv("LOCAL_LLM_ENDPOINT", "http://localhost:11434")
            
            return LocalLLMSummarizer(
                model=model,
                base_url=base_url
            )
            
        elif provider == "mock":
            latency_ms = int(os.getenv("MOCK_LATENCY_MS", "100"))
            return MockSummarizer(latency_ms=latency_ms)
            
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported providers: openai, azure, local, mock"
            )
