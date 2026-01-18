# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for identity provider initialization and configuration."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_Inmemory,
)
from copilot_config.generated.adapters.logger import (
    AdapterConfig_Logger,
    DriverConfig_Logger_Stdout,
)
from copilot_config.generated.adapters.metrics import (
    AdapterConfig_Metrics,
    DriverConfig_Metrics_Noop,
)
from copilot_config.generated.adapters.oidc_providers import (
    AdapterConfig_OidcProviders,
    CompositeConfig_OidcProviders,
    DriverConfig_OidcProviders_Github,
    DriverConfig_OidcProviders_Google,
    DriverConfig_OidcProviders_Microsoft,
)
from copilot_config.generated.adapters.secret_provider import (
    AdapterConfig_SecretProvider,
    DriverConfig_SecretProvider_Local,
)
from copilot_config.generated.services.auth import ServiceConfig_Auth, ServiceSettings_Auth

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.service import AuthService


class TestProviderInitialization:
    """Test identity provider initialization with different configurations."""

    @pytest.fixture
    def mock_config(self):
        """Create a typed configuration."""
        settings = ServiceSettings_Auth(
            issuer="http://localhost:8090",
            audiences="copilot-for-consensus",
            jwt_algorithm="RS256",
            jwt_key_id="default",
            jwt_default_expiry=1800,
            max_skew_seconds=90,
            # Provide dummy keys so AuthService can initialize.
            jwt_private_key="-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----\n",
            jwt_public_key="-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n",
            jwt_secret_key=None,
            role_store_schema_dir=None,
            auto_approve_roles="",
            auto_approve_enabled=False,
            first_user_auto_promotion_enabled=False,
        )

        return ServiceConfig_Auth(
            service_settings=settings,
            document_store=AdapterConfig_DocumentStore(
                doc_store_type="inmemory",
                driver=DriverConfig_DocumentStore_Inmemory(),
            ),
            logger=AdapterConfig_Logger(
                logger_type="stdout",
                driver=DriverConfig_Logger_Stdout(),
            ),
            metrics=AdapterConfig_Metrics(
                metrics_type="noop",
                driver=DriverConfig_Metrics_Noop(),
            ),
            oidc_providers=AdapterConfig_OidcProviders(oidc_providers=CompositeConfig_OidcProviders()),
            secret_provider=AdapterConfig_SecretProvider(
                secret_provider_type="local",
                driver=DriverConfig_SecretProvider_Local(),
            ),
        )

    def _create_mock_identity_provider(self):
        """Create a mock identity provider with all required methods."""
        provider = MagicMock()
        provider.discover = MagicMock()
        provider.build_pkce_pair = MagicMock(return_value=("verifier", "challenge"))
        provider.get_authorization_url = MagicMock(return_value=("https://auth.example.com", "state", "nonce"))
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
        mock_config.oidc_providers = AdapterConfig_OidcProviders(
            oidc_providers=CompositeConfig_OidcProviders(
                github=DriverConfig_OidcProviders_Github(
                    github_client_id="test_client_id",
                    github_client_secret="test_client_secret",
                    github_redirect_uri="http://localhost:8090/callback",
                )
            )
        )

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
        mock_config.oidc_providers = AdapterConfig_OidcProviders(
            oidc_providers=CompositeConfig_OidcProviders(
                google=DriverConfig_OidcProviders_Google(
                    google_client_id="test_client_id.apps.googleusercontent.com",
                    google_client_secret="test_client_secret",
                    google_redirect_uri="http://localhost:8090/callback",
                )
            )
        )

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
        mock_config.oidc_providers = AdapterConfig_OidcProviders(
            oidc_providers=CompositeConfig_OidcProviders(
                microsoft=DriverConfig_OidcProviders_Microsoft(
                    microsoft_client_id="test_client_id",
                    microsoft_client_secret="test_client_secret",
                    microsoft_redirect_uri="http://localhost:8090/callback",
                )
            )
        )

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
        mock_config.oidc_providers = AdapterConfig_OidcProviders(
            oidc_providers=CompositeConfig_OidcProviders(
                github=DriverConfig_OidcProviders_Github(
                    github_client_id="github_id",
                    github_client_secret="github_secret",
                    github_redirect_uri="http://localhost:8090/callback",
                ),
                google=DriverConfig_OidcProviders_Google(
                    google_client_id="google_id",
                    google_client_secret="google_secret",
                    google_redirect_uri="http://localhost:8090/callback",
                ),
            )
        )

        call_count = 0

        def mock_create_provider(provider_name, driver_config, *, issuer=None):
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

    def test_service_starts_with_partial_provider_init_failure(self, mock_config, monkeypatch):
        """Service should start with providers that initialize successfully."""
        monkeypatch.setattr(Path, "write_text", lambda self, content: None)
        monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)

        class MockJWTManager:
            def __init__(self, **kwargs):
                pass

        from app import service

        original_jwt_manager = service.JWTManager
        service.JWTManager = MockJWTManager

        mock_config.oidc_providers = AdapterConfig_OidcProviders(
            oidc_providers=CompositeConfig_OidcProviders(
                github=DriverConfig_OidcProviders_Github(
                    github_client_id="test_client_id",
                    github_client_secret="test_client_secret",
                    github_redirect_uri="http://localhost:8090/callback",
                ),
                google=DriverConfig_OidcProviders_Google(
                    google_client_id="test_client_id.apps.googleusercontent.com",
                    google_client_secret="test_client_secret",
                    google_redirect_uri="http://localhost:8090/callback",
                ),
            )
        )

        good_provider = self._create_mock_identity_provider()

        def _create_provider(provider_type: str, *_args, **_kwargs):
            if provider_type == "github":
                raise RuntimeError("boom")
            return good_provider

        with patch("app.service.create_identity_provider", side_effect=_create_provider):
            auth_svc = AuthService(config=mock_config)

            assert "google" in auth_svc.providers
            assert auth_svc.providers["google"] is good_provider
            assert "github" not in auth_svc.providers

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
        mock_config.oidc_providers = AdapterConfig_OidcProviders(
            oidc_providers=CompositeConfig_OidcProviders(
                github=DriverConfig_OidcProviders_Github(
                    github_client_id="test_id",
                    github_client_secret="test_secret",
                    github_redirect_uri=custom_redirect,
                )
            )
        )

        captured_config = {}

        def capture_create_provider(provider_name, driver_config, *, issuer=None):
            captured_config[provider_name] = driver_config
            return self._create_mock_identity_provider()

        with patch("app.service.create_identity_provider", side_effect=capture_create_provider):
            AuthService(config=mock_config)

            # Verify custom redirect URI was passed to the factory
            assert "github" in captured_config
            assert captured_config["github"].github_redirect_uri == custom_redirect

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
        mock_config.oidc_providers = AdapterConfig_OidcProviders(
            oidc_providers=CompositeConfig_OidcProviders(
                github=DriverConfig_OidcProviders_Github(
                    github_client_id="test_id",
                    github_client_secret="test_secret",
                )
            )
        )

        captured_config = {}

        def capture_create_provider(provider_name, driver_config, *, issuer=None):
            captured_config[provider_name] = driver_config
            return self._create_mock_identity_provider()

        with patch("app.service.create_identity_provider", side_effect=capture_create_provider):
            AuthService(config=mock_config)

            # Verify default redirect URI uses service issuer
            assert "github" in captured_config
            assert captured_config["github"].github_redirect_uri == f"{mock_config.service_settings.issuer}/callback"

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

        mock_config.oidc_providers = AdapterConfig_OidcProviders(
            oidc_providers=CompositeConfig_OidcProviders(
                github=DriverConfig_OidcProviders_Github(
                    github_client_id="test_id",
                    github_client_secret="test_secret",
                )
            )
        )

        # Make factory raise an exception
        def raise_error(provider_name, driver_config, *, issuer=None):
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

        mock_config.oidc_providers = AdapterConfig_OidcProviders(
            oidc_providers=CompositeConfig_OidcProviders(
                github=DriverConfig_OidcProviders_Github(
                    github_client_id="test_id",
                    github_client_secret="test_secret",
                    github_redirect_uri="http://localhost:8090/callback",
                )
            )
        )

        with patch("app.service.create_identity_provider") as mock_create:
            mock_create.return_value = self._create_mock_identity_provider()

            AuthService(config=mock_config)

            # Verify factory was called with driver_name and driver_config
            mock_create.assert_called()
            call_args = mock_create.call_args

            assert call_args.args[0] == "github"
            driver_cfg = call_args.args[1]
            assert driver_cfg.github_client_id == "test_id"
            assert driver_cfg.github_redirect_uri == "http://localhost:8090/callback"
            assert call_args.kwargs.get("issuer") == "http://localhost:8090"

        service.JWTManager = original_jwt_manager
