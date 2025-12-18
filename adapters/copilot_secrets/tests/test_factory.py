# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for secret provider factory."""

import pytest
import tempfile
from pathlib import Path

from copilot_secrets import (
    create_secret_provider,
    LocalFileSecretProvider,
    SecretProviderError,
)


class TestFactory:
    """Test suite for secret provider factory."""
    
    def test_create_local_provider(self):
        """Test creation of local file provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = create_secret_provider("local", base_path=tmpdir)
            assert isinstance(provider, LocalFileSecretProvider)
            assert provider.base_path == Path(tmpdir)
    
    def test_create_unknown_provider(self):
        """Test creation with unknown provider type."""
        with pytest.raises(SecretProviderError, match="Unknown provider type"):
            create_secret_provider("unknown_type")
    
    def test_factory_forwards_kwargs(self):
        """Test that factory forwards kwargs to provider constructor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = create_secret_provider("local", base_path=tmpdir)
            assert provider.base_path == Path(tmpdir)
