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
        backend: Embedding backend type. If None, reads from EMBEDDING_BACKEND env var.
                Options: 'mock', 'sentencetransformers', 'openai', 'azure', 'huggingface'
        model: Model name or identifier. If None, uses backend-specific defaults.
        **kwargs: Additional provider-specific parameters
        
    Returns:
        EmbeddingProvider instance
        
    Raises:
        ValueError: If backend is unknown or required configuration is missing
    """
    # Get backend from parameter or environment
    if backend is None:
        backend = os.getenv("EMBEDDING_BACKEND", "sentencetransformers")
    
    backend = backend.lower()
    logger.info(f"Creating embedding provider with backend: {backend}")
    
    if backend == "mock":
        dimension = kwargs.get("dimension") or int(os.getenv("EMBEDDING_DIMENSION", "384"))
        return MockEmbeddingProvider(dimension=dimension)
    
    elif backend == "sentencetransformers":
        model = model or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        device = kwargs.get("device") or os.getenv("DEVICE", "cpu")
        cache_dir = kwargs.get("cache_dir") or os.getenv("MODEL_CACHE_DIR")
        
        return SentenceTransformerEmbeddingProvider(
            model_name=model,
            device=device,
            cache_dir=cache_dir
        )
    
    elif backend == "openai":
        api_key = kwargs.get("api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("api_key parameter or OPENAI_API_KEY environment variable is required for OpenAI backend")
        
        model = model or os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=model
        )
    
    elif backend == "azure":
        api_key = kwargs.get("api_key") or os.getenv("AZURE_OPENAI_KEY")
        api_base = kwargs.get("api_base") or os.getenv("AZURE_OPENAI_ENDPOINT")
        api_version = kwargs.get("api_version") or os.getenv("AZURE_OPENAI_API_VERSION")
        deployment_name = kwargs.get("deployment_name") or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        
        if not api_key:
            raise ValueError("api_key parameter or AZURE_OPENAI_KEY environment variable is required for Azure backend")
        if not api_base:
            raise ValueError("api_base parameter or AZURE_OPENAI_ENDPOINT environment variable is required for Azure backend")
        
        model = model or deployment_name or "text-embedding-ada-002"
        
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=model,
            api_base=api_base,
            api_version=api_version,
            deployment_name=deployment_name
        )
    
    elif backend == "huggingface":
        model = model or os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        device = kwargs.get("device") or os.getenv("DEVICE", "cpu")
        cache_dir = kwargs.get("cache_dir") or os.getenv("MODEL_CACHE_DIR")
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
