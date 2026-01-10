# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""SentenceTransformer embedding provider."""

import logging

from copilot_config import DriverConfig

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)


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

    @classmethod
    def from_config(cls, driver_config: DriverConfig):
        """Create provider from configuration.
        
        Configuration defaults are defined in schema:
        docs/schemas/configs/adapters/drivers/embedding_backend/sentencetransformers.json
        
        Args:
            driver_config: Configuration object with attributes:
                          - model_name: Model name
                          - device: Compute device (cpu or cuda)
                          - cache_dir: Cache directory (optional)
        
        Returns:
            Configured SentenceTransformerEmbeddingProvider
        
        Raises:
            ValueError: If required attributes are missing
        """
        model_name = driver_config.model_name
        device = driver_config.device
        cache_dir = driver_config.cache_dir
        return cls(model_name=str(model_name), device=str(device), cache_dir=cache_dir)

    def embed(self, text: str) -> list[float]:
        """Generate embeddings using SentenceTransformer.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If text is None or empty
        """
        if not text.strip():
            raise ValueError("Text cannot be empty or whitespace-only")

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
