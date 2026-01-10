# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Mock embedding provider for testing."""

import logging
from copilot_config import DriverConfig

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int):
        """Initialize mock provider.

        Args:
            dimension: Dimension of the embedding vector
        """
        self.dimension = dimension
        logger.info(f"Initialized MockEmbeddingProvider with dimension={dimension}")

    @classmethod
    def from_config(cls, driver_config: DriverConfig) -> "MockEmbeddingProvider":
        """Create provider from configuration.

        Configuration defaults are defined in schema:
        docs/schemas/configs/adapters/drivers/embedding_backend/mock.json

        Args:
            driver_config: Configuration object with attribute:
                          - dimension: Embedding dimension

        Returns:
            Configured MockEmbeddingProvider

        Raises:
            ValueError: If dimension is missing or invalid
        """
        dimension = driver_config.dimension
        if dimension is None:
            raise ValueError(
                "dimension parameter is required for mock backend. "
                "Specify the embedding dimension (e.g., 384 for all-MiniLM-L6-v2)"
            )
        return cls(dimension=int(dimension))

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
