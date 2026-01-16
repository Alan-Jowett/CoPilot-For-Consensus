# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""HuggingFace Transformers embedding provider."""

import logging

from copilot_config.generated.adapters.embedding_backend import DriverConfig_EmbeddingBackend_Huggingface

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)

class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """HuggingFace embedding provider for Transformers models."""

    def __init__(
        self,
        model_name: str,
        device: str,
        max_length: int,
        cache_dir: str | None = None
    ):
        """Initialize HuggingFace embedding provider.

        Args:
            model_name: Name of the HuggingFace model
            device: Device to run inference on (cpu, cuda, mps)
            max_length: Maximum sequence length for tokenization
            cache_dir: Directory to cache models
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

    @classmethod
    def from_config(
        cls, driver_config: DriverConfig_EmbeddingBackend_Huggingface
    ) -> "HuggingFaceEmbeddingProvider":
        """Create provider from configuration.

        Configuration defaults are defined in schema:
        docs/schemas/configs/adapters/drivers/embedding_backend/embedding_huggingface.json

        Args:
            driver_config: Configuration object with attributes:
                          - model_name: Model name (required)
                          - device: Compute device (required)
                          - cache_dir: Cache directory (optional)
                          - max_length: Max token length (default: 512)

        Returns:
            Configured HuggingFaceEmbeddingProvider
        """
        return cls(
            model_name=driver_config.model_name,
            device=driver_config.device,
            max_length=int(driver_config.max_length),
            cache_dir=driver_config.cache_dir,
        )

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
