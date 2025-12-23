# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Embedding provider abstraction layer."""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate embeddings for the given text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int = 384):
        """Initialize mock provider.

        Args:
            dimension: Dimension of the embedding vector
        """
        self.dimension = dimension
        logger.info(f"Initialized MockEmbeddingProvider with dimension={dimension}")

    def embed(self, text: str) -> list[float]:
        """Generate mock embeddings based on text hash.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the mock embedding vector

        Raises:
            ValueError: If text is None or empty
        """
        if text is None:
            raise ValueError("Text cannot be None")
        if not isinstance(text, str):
            raise ValueError(f"Text must be a string, got {type(text).__name__}")
        if not text.strip():
            raise ValueError("Text cannot be empty or whitespace-only")

        # Generate deterministic mock embeddings based on text hash
        # Uses modulo arithmetic to create different values for each dimension
        # Formula ensures values are in [0, 1] range and deterministic for same text
        text_hash = hash(text)
        return [(text_hash % (i + 1)) / (i + 1) for i in range(self.dimension)]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """SentenceTransformer embedding provider for local models."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        cache_dir: str | None = None
    ):
        """Initialize SentenceTransformer provider.

        Args:
            model_name: Name of the SentenceTransformer model
            device: Device to run inference on (cpu, cuda, mps)
            cache_dir: Directory to cache models
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for SentenceTransformerEmbeddingProvider. "
                "Install it with: pip install sentence-transformers"
            )

        self.model_name = model_name
        self.device = device
        self.cache_dir = cache_dir

        logger.info(f"Loading SentenceTransformer model: {model_name} on device: {device}")
        self.model = SentenceTransformer(
            model_name,
            device=device,
            cache_folder=cache_dir
        )
        logger.info("SentenceTransformer model loaded successfully")

    def embed(self, text: str) -> list[float]:
        """Generate embeddings using SentenceTransformer.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If text is None or empty
        """
        if text is None:
            raise ValueError("Text cannot be None")
        if not isinstance(text, str):
            raise ValueError(f"Text must be a string, got {type(text).__name__}")
        if not text.strip():
            raise ValueError("Text cannot be empty or whitespace-only")

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()


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

    def embed(self, text: str) -> list[float]:
        """Generate embeddings using OpenAI API.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If text is None or empty
        """
        if text is None:
            raise ValueError("Text cannot be None")
        if not isinstance(text, str):
            raise ValueError(f"Text must be a string, got {type(text).__name__}")
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


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """HuggingFace embedding provider for Transformers models."""

    # Default maximum sequence length for tokenization
    DEFAULT_MAX_LENGTH = 512

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
        cache_dir: str | None = None,
        max_length: int = DEFAULT_MAX_LENGTH
    ):
        """Initialize HuggingFace embedding provider.

        Args:
            model_name: Name of the HuggingFace model
            device: Device to run inference on (cpu, cuda, mps)
            cache_dir: Directory to cache models
            max_length: Maximum sequence length for tokenization
        """
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError:
            raise ImportError(
                "transformers and torch are required for HuggingFaceEmbeddingProvider. "
                "Install them with: pip install transformers torch"
            )

        self.model_name = model_name
        self.device = device
        self.cache_dir = cache_dir
        self.max_length = max_length
        self.torch = torch

        logger.info(f"Loading HuggingFace model: {model_name} on device: {device}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=cache_dir
        )
        self.model = AutoModel.from_pretrained(
            model_name,
            cache_dir=cache_dir
        ).to(device)
        logger.info("HuggingFace model loaded successfully")

    def embed(self, text: str) -> list[float]:
        """Generate embeddings using HuggingFace Transformers.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If text is None or empty

        Note:
            This method performs CPU-to-GPU and GPU-to-CPU transfers on each call.
            For high-frequency embedding generation, consider batch processing for
            better performance in production use cases.
        """
        if text is None:
            raise ValueError("Text cannot be None")
        if not isinstance(text, str):
            raise ValueError(f"Text must be a string, got {type(text).__name__}")
        if not text.strip():
            raise ValueError("Text cannot be empty or whitespace-only")

        # Tokenize and encode
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_length
        ).to(self.device)

        # Generate embeddings
        with self.torch.no_grad():
            outputs = self.model(**inputs)

        # Use mean pooling on token embeddings
        embeddings = outputs.last_hidden_state.mean(dim=1)

        return embeddings.cpu().numpy()[0].tolist()
