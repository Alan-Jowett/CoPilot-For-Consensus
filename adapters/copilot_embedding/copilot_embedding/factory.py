# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating embedding providers based on configuration."""

import os
import logging
from typing import Optional

from .providers import (
    EmbeddingProvider,
    MockEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    OpenAIEmbeddingProvider,
    HuggingFaceEmbeddingProvider,
)

logger = logging.getLogger(__name__)


def create_embedding_provider(
    backend: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> EmbeddingProvider:
    """Create an embedding provider based on configuration.
    
    Args:
        backend: Embedding backend type (required).
                Options: 'mock', 'sentencetransformers', 'openai', 'azure', 'huggingface'
        model: Model name or identifier. Required for most backends except 'mock'.
        **kwargs: Additional provider-specific parameters
        
    Returns:
        EmbeddingProvider instance
        
    Raises:
        ValueError: If backend is unknown or required configuration is missing
    """
    if not backend:
        raise ValueError(
            "backend parameter is required. "
            "Must be one of: mock, sentencetransformers, openai, azure, huggingface"
        )
    
    backend = backend.lower()
    logger.info(f"Creating embedding provider with backend: {backend}")
    
    if backend == "mock":
        dimension = kwargs.get("dimension")
        if dimension is None:
            raise ValueError(
                "dimension parameter is required for mock backend. "
                "Specify the embedding dimension (e.g., 384 for all-MiniLM-L6-v2)"
            )
        return MockEmbeddingProvider(dimension=dimension)
    
    elif backend == "sentencetransformers":
        if not model:
            raise ValueError(
                "model parameter is required for sentencetransformers backend. "
                "Specify a model name (e.g., 'all-MiniLM-L6-v2')"
            )
        device = kwargs.get("device")
        if device is None:
            raise ValueError(
                "device parameter is required for sentencetransformers backend. "
                "Specify 'cpu' or 'cuda'"
            )
        cache_dir = kwargs.get("cache_dir")
        
        return SentenceTransformerEmbeddingProvider(
            model_name=model,
            device=device,
            cache_dir=cache_dir
        )
    
    elif backend == "openai":
        api_key = kwargs.get("api_key")
        if not api_key:
            raise ValueError(
                "api_key parameter is required for OpenAI backend. "
                "Provide the API key explicitly"
            )
        
        if not model:
            raise ValueError(
                "model parameter is required for OpenAI backend. "
                "Specify a model name (e.g., 'text-embedding-ada-002')"
            )
        
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=model
        )
    
    elif backend == "azure":
        api_key = kwargs.get("api_key")
        if not api_key:
            raise ValueError(
                "api_key parameter is required for Azure backend. "
                "Provide the Azure OpenAI API key explicitly"
            )
        
        api_base = kwargs.get("api_base")
        if not api_base:
            raise ValueError(
                "api_base parameter is required for Azure backend. "
                "Provide the Azure OpenAI endpoint explicitly"
            )
        
        api_version = kwargs.get("api_version")
        deployment_name = kwargs.get("deployment_name")
        
        if not model and not deployment_name:
            raise ValueError(
                "Either model or deployment_name parameter is required for Azure backend. "
                "Specify the model or deployment name"
            )
        
        # Use deployment_name as model if model not provided
        model = model or deployment_name
        
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=model,
            api_base=api_base,
            api_version=api_version,
            deployment_name=deployment_name
        )
    
    elif backend == "huggingface":
        if not model:
            raise ValueError(
                "model parameter is required for huggingface backend. "
                "Specify a model name (e.g., 'sentence-transformers/all-MiniLM-L6-v2')"
            )
        device = kwargs.get("device")
        if device is None:
            raise ValueError(
                "device parameter is required for huggingface backend. "
                "Specify 'cpu' or 'cuda'"
            )
        cache_dir = kwargs.get("cache_dir")
        max_length = kwargs.get("max_length")
        
        return HuggingFaceEmbeddingProvider(
            model_name=model,
            device=device,
            cache_dir=cache_dir,
            max_length=max_length
        )
    
    else:
        raise ValueError(
            f"Unknown embedding backend: {backend}. "
            f"Supported backends: mock, sentencetransformers, openai, azure, huggingface"
        )
