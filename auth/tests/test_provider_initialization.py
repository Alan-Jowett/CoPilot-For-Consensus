# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for identity provider initialization and configuration."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.service import AuthService


class TestProviderInitialization:
    """Test identity provider initialization with different configurations."""

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
        # Provide dummy keys so AuthService can initialize.
        config.jwt_private_key = "-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----\n"
        config.jwt_public_key = "-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
        config.jwt_secret_key = None
        config.role_store_schema_dir = None
        config.auto_approve_roles = ""
        config.auto_approve_enabled = False
        config.first_user_auto_promotion_enabled = False

        # Configure providers via the composite adapter
        oidc_adapter = MagicMock()
        oidc_adapter.driver_name = "multi"
        oidc_adapter.driver_config = MagicMock()
        oidc_adapter.driver_config.config = {}
        config._oidc_adapter = oidc_adapter

        def get_adapter(adapter_type: str):
            if adapter_type == "oidc_providers":
                return config._oidc_adapter
            return None

        config.get_adapter = get_adapter
        return config

    def _create_mock_identity_provider(self):
        """Create a mock identity provider with all required methods."""
        provider = MagicMock()
        provider.discover = MagicMock()
        provider.build_pkce_pair = MagicMock(return_value=("verifier", "challenge"))
        provider.get_authorization_url = MagicMock(
            return_value=("https://auth.example.com", "state", "nonce")
        )
        provider.exchange_code_for_token = MagicMock(
            return_value={"access_token": "token123", "id_token": "idtoken123"}
        )
        
        # Mock user object
        user = MagicMock()
        user.sub = "user123"
        user.email = "user@example.com"
        user.name = "Test User"
        user.roles = []
        
        provider.validate_and_get_user = MagicMock(return_value=user)
        return provider

    def test_github_provider_initialization(self, mock_config, monkeypatch):
        """Test initialization with GitHub provider configuration."""
        # Patch JWT and file operations
        monkeypatch.setattr(Path, "write_text", lambda self, content: None)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
        
        class MockJWTManager:
            def __init__(self, **kwargs):
                pass

        from app import service
        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager

        # Configure GitHub provider
        mock_config._oidc_adapter.driver_config.config = {
            "github": {
                "github_client_id": "test_client_id",
                "github_client_secret": "test_client_secret",
                "github_redirect_uri": "http://localhost:8090/callback",
            }
        }

        # Mock create_identity_provider
        mock_provider = self._create_mock_identity_provider()
        with patch("app.service.create_identity_provider", return_value=mock_provider):
            auth_svc = AuthService(config=mock_config)

            # Verify GitHub provider was initialized
            assert "github" in auth_svc.providers
            assert auth_svc.providers["github"] is mock_provider
            mock_provider.discover.assert_called_once()

        service.JWTManager = original_jwt_manager

    def test_google_provider_initialization(self, mock_config, monkeypatch):
        """Test initialization with Google provider configuration."""
        monkeypatch.setattr(Path, "write_text", lambda self, content: None)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
        
        class MockJWTManager:
            def __init__(self, **kwargs):
                pass

        from app import service
        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager

        # Configure Google provider
        mock_config._oidc_adapter.driver_config.config = {
            "google": {
                "google_client_id": "test_client_id.apps.googleusercontent.com",
                "google_client_secret": "test_client_secret",
                "google_redirect_uri": "http://localhost:8090/callback",
            }
        }

        mock_provider = self._create_mock_identity_provider()
        with patch("app.service.create_identity_provider", return_value=mock_provider):
            auth_svc = AuthService(config=mock_config)

            assert "google" in auth_svc.providers
            assert auth_svc.providers["google"] is mock_provider

        service.JWTManager = original_jwt_manager

    def test_microsoft_provider_initialization(self, mock_config, monkeypatch):
        """Test initialization with Microsoft provider configuration."""
        monkeypatch.setattr(Path, "write_text", lambda self, content: None)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
        
        class MockJWTManager:
            def __init__(self, **kwargs):
                pass

        from app import service
        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager

        # Configure Microsoft provider
        mock_config._oidc_adapter.driver_config.config = {
            "microsoft": {
                "microsoft_client_id": "test_client_id",
                "microsoft_client_secret": "test_client_secret",
                "microsoft_redirect_uri": "http://localhost:8090/callback",
            }
        }

        mock_provider = self._create_mock_identity_provider()
        with patch("app.service.create_identity_provider", return_value=mock_provider):
            auth_svc = AuthService(config=mock_config)

            assert "microsoft" in auth_svc.providers
            assert auth_svc.providers["microsoft"] is mock_provider

        service.JWTManager = original_jwt_manager

    def test_multiple_providers_initialization(self, mock_config, monkeypatch):
        """Test initialization with multiple providers configured."""
        monkeypatch.setattr(Path, "write_text", lambda self, content: None)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
        
        class MockJWTManager:
            def __init__(self, **kwargs):
                pass

        from app import service
        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager

        # Configure multiple providers
        mock_config._oidc_adapter.driver_config.config = {
            "github": {
                "github_client_id": "github_id",
                "github_client_secret": "github_secret",
                "github_redirect_uri": "http://localhost:8090/callback",
            },
            "google": {
                "google_client_id": "google_id",
                "google_client_secret": "google_secret",
                "google_redirect_uri": "http://localhost:8090/callback",
            },
        }

        call_count = 0
        def mock_create_provider(driver_name, driver_config):
            nonlocal call_count
            call_count += 1
            return self._create_mock_identity_provider()

        with patch("app.service.create_identity_provider", side_effect=mock_create_provider):
            auth_svc = AuthService(config=mock_config)

            # Verify both providers were initialized
            assert len(auth_svc.providers) == 2
            assert "github" in auth_svc.providers
            assert "google" in auth_svc.providers
            assert call_count == 2

        service.JWTManager = original_jwt_manager

    def test_provider_initialization_with_custom_redirect_uri(self, mock_config, monkeypatch):
        """Test that custom redirect URIs from config are preserved."""
        monkeypatch.setattr(Path, "write_text", lambda self, content: None)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
        
        class MockJWTManager:
            def __init__(self, **kwargs):
                pass

        from app import service
        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager

        custom_redirect = "https://custom.redirect.example.com/callback"
        mock_config._oidc_adapter.driver_config.config = {
            "github": {
                "github_client_id": "test_id",
                "github_client_secret": "test_secret",
                "github_redirect_uri": custom_redirect,
            }
        }

        captured_config = {}
        def capture_create_provider(driver_name, driver_config):
            captured_config[driver_name] = driver_config
            return self._create_mock_identity_provider()

        with patch("app.service.create_identity_provider", side_effect=capture_create_provider):
            AuthService(config=mock_config)

            # Verify custom redirect URI was passed to the factory
            assert "github" in captured_config
            assert captured_config["github"]["redirect_uri"] == custom_redirect

        service.JWTManager = original_jwt_manager

    def test_provider_initialization_uses_issuer_as_default_redirect(self, mock_config, monkeypatch):
        """Test that service issuer is used as default redirect URI if not configured."""
        monkeypatch.setattr(Path, "write_text", lambda self, content: None)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
        
        class MockJWTManager:
            def __init__(self, **kwargs):
                pass

        from app import service
        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager

        # Provider config without explicit redirect_uri
        mock_config._oidc_adapter.driver_config.config = {
            "github": {
                "github_client_id": "test_id",
                "github_client_secret": "test_secret",
            }
        }

        captured_config = {}
        def capture_create_provider(driver_name, driver_config):
            captured_config[driver_name] = driver_config
            return self._create_mock_identity_provider()

        with patch("app.service.create_identity_provider", side_effect=capture_create_provider):
            AuthService(config=mock_config)

            # Verify default redirect URI uses service issuer
            assert "github" in captured_config
            assert captured_config["github"]["redirect_uri"] == f"{mock_config.issuer}/callback"

        service.JWTManager = original_jwt_manager

    def test_provider_initialization_failure_is_logged(self, mock_config, monkeypatch):
        """Test that provider initialization failures are caught and logged."""
        monkeypatch.setattr(Path, "write_text", lambda self, content: None)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
        
        class MockJWTManager:
            def __init__(self, **kwargs):
                pass

        from app import service
        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager

        mock_config._oidc_adapter.driver_config.config = {
            "github": {
                "github_client_id": "test_id",
                "github_client_secret": "test_secret",
            }
        }

        # Make factory raise an exception
        def raise_error(driver_name, driver_config):
            raise ValueError("Invalid configuration")

        with patch("app.service.create_identity_provider", side_effect=raise_error):
            with patch("app.service.logger") as mock_logger:
                auth_svc = AuthService(config=mock_config)

                # Verify the service continues but provider not registered
                assert "github" not in auth_svc.providers
                # Verify error was logged
                mock_logger.error.assert_called()

        service.JWTManager = original_jwt_manager

    def test_provider_creation_passes_driver_name_and_config(self, mock_config, monkeypatch):
        """Test that create_identity_provider is called with correct driver_name and driver_config."""
        monkeypatch.setattr(Path, "write_text", lambda self, content: None)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
        
        class MockJWTManager:
            def __init__(self, **kwargs):
                pass

        from app import service
        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager

        provider_config = {
            "github_client_id": "test_id",
            "github_client_secret": "test_secret",
            "github_redirect_uri": "http://localhost:8090/callback",
        }
        
        mock_config._oidc_adapter.driver_config.config = {
            "github": provider_config
        }

        with patch("app.service.create_identity_provider") as mock_create:
            mock_create.return_value = self._create_mock_identity_provider()
            
            AuthService(config=mock_config)

            # Verify factory was called with driver_name and driver_config
            mock_create.assert_called()
            call_args = mock_create.call_args
            
            # Check keyword arguments
            assert call_args.kwargs.get("driver_name") == "github"
            assert "driver_config" in call_args.kwargs
            # driver_config should include all the provider config plus redirect_uri
            driver_cfg = call_args.kwargs.get("driver_config")
            assert driver_cfg["github_client_id"] == "test_id"
            assert driver_cfg["redirect_uri"] == "http://localhost:8090/callback"

        service.JWTManager = original_jwt_manager
