# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for provider error messages and availability checking."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.service import AuthService


class TestProviderErrors:
    """Test provider error messages and availability."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock()
        config.issuer = "http://localhost:8090"
        config.audiences = "copilot-for-consensus"
        config.jwt_algorithm = "RS256"
        config.jwt_key_id = "default"
        config.jwt_default_expiry = 1800
        config.max_skew_seconds = 90
        config.jwt_private_key = None
        config.jwt_public_key = None
        config.jwt_secret_key = None
        config.github_client_id = None
        config.google_client_id = None
        config.microsoft_client_id = None
        return config

    @pytest.fixture
    def auth_service_no_providers(self, mock_config, monkeypatch):
        """Create an auth service with no providers configured."""
        # Mock JWT key paths to avoid file system access
        def mock_write_text(self, content):
            pass
        
        monkeypatch.setattr(Path, "write_text", mock_write_text)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
        
        # Mock JWTManager since we don't need it for these tests
        class MockJWTManager:
            def __init__(self, **kwargs):
                pass
        
        from app import service
        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager
        
        # Create service
        auth_svc = AuthService(config=mock_config)
        
        # Restore original
        service.JWTManager = original_jwt_manager
        
        return auth_svc

    @pytest.mark.asyncio
    async def test_error_message_for_unconfigured_google(self, auth_service_no_providers):
        """Test that attempting to use Google provider gives helpful error when not configured."""
        with pytest.raises(ValueError) as exc_info:
            await auth_service_no_providers.initiate_login(
                provider="google",
                audience="test-audience"
            )
        
        error_msg = str(exc_info.value)
        assert "google" in error_msg.lower()
        assert "not configured" in error_msg.lower()
        assert "oauth credentials" in error_msg.lower()
        assert "documentation" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_error_message_for_unconfigured_microsoft(self, auth_service_no_providers):
        """Test that attempting to use Microsoft provider gives helpful error when not configured."""
        with pytest.raises(ValueError) as exc_info:
            await auth_service_no_providers.initiate_login(
                provider="microsoft",
                audience="test-audience"
            )
        
        error_msg = str(exc_info.value)
        assert "microsoft" in error_msg.lower()
        assert "not configured" in error_msg.lower()
        assert "oauth credentials" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_error_message_for_unknown_provider(self, auth_service_no_providers):
        """Test that using an unknown provider gives appropriate error."""
        with pytest.raises(ValueError) as exc_info:
            await auth_service_no_providers.initiate_login(
                provider="unknown-provider",
                audience="test-audience"
            )
        
        error_msg = str(exc_info.value)
        assert "unknown provider" in error_msg.lower()
        assert "supported providers" in error_msg.lower()
        # Should mention the three supported providers
        assert "github" in error_msg.lower()
        assert "google" in error_msg.lower()
        assert "microsoft" in error_msg.lower()

    def test_no_providers_configured_initially(self, auth_service_no_providers):
        """Test that service starts with no providers when none are configured."""
        assert len(auth_service_no_providers.providers) == 0

    @pytest.fixture
    def auth_service_with_github(self, mock_config, monkeypatch):
        """Create an auth service with only GitHub configured."""
        mock_config.github_client_id = "test_client_id"
        mock_config.github_client_secret = "test_client_secret"
        
        # Mock to avoid actual provider initialization
        def mock_write_text(self, content):
            pass
        
        monkeypatch.setattr(Path, "write_text", mock_write_text)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
        
        # Mock JWTManager
        class MockJWTManager:
            def __init__(self, **kwargs):
                pass
        
        from app import service
        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager
        
        # Mock create_identity_provider to return a mock provider
        original_create = service.create_identity_provider
        def mock_create(**kwargs):
            mock_provider = MagicMock()
            mock_provider.discover = MagicMock()
            return mock_provider
        service.create_identity_provider = mock_create
        
        # Create service
        auth_svc = AuthService(config=mock_config)
        
        # Restore originals
        service.JWTManager = original_jwt_manager
        service.create_identity_provider = original_create
        
        return auth_svc

    @pytest.mark.asyncio
    async def test_configured_provider_listed_in_error(self, auth_service_with_github):
        """Test that configured providers are listed in error message."""
        with pytest.raises(ValueError) as exc_info:
            await auth_service_with_github.initiate_login(
                provider="google",
                audience="test-audience"
            )
        
        error_msg = str(exc_info.value)
        # Should mention that GitHub is configured
        assert "github" in error_msg.lower()

    def test_github_provider_is_initialized(self, auth_service_with_github):
        """Test that GitHub provider is in the providers dict when configured."""
        assert "github" in auth_service_with_github.providers
        assert len(auth_service_with_github.providers) == 1
