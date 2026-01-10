# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for EmbeddingProvider abstract base class."""

import pytest
from copilot_embedding.base import EmbeddingProvider


class TestEmbeddingProvider:
    """Tests for EmbeddingProvider abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that abstract base class cannot be instantiated."""
        with pytest.raises(TypeError):
            EmbeddingProvider()
