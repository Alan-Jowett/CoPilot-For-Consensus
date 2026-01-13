# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for startup dependency validation in auth service."""

import os
import sys
from unittest.mock import patch

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
)
from copilot_config.generated.adapters.secret_provider import (
    AdapterConfig_SecretProvider,
    DriverConfig_SecretProvider_Local,
)
from copilot_config.generated.adapters.jwt_signer import (
    AdapterConfig_JwtSigner,
    DriverConfig_JwtSigner_Local,
)
from copilot_config.generated.services.auth import ServiceConfig_Auth, ServiceSettings_Auth

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_main_imports_successfully():
    """Test that main.py imports successfully without errors."""
    # Auth service has a unique structure - just verify it imports
    import main as auth_main

    assert auth_main is not None

@pytest.mark.anyio
async def test_lifespan_starts_with_minimal_typed_config():
    """Ensure FastAPI lifespan starts with a minimal typed config."""
    import main as auth_main

    minimal = ServiceConfig_Auth(
        service_settings=ServiceSettings_Auth(
            issuer="http://localhost:8090",
        ),
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
        oidc_providers=AdapterConfig_OidcProviders(
            oidc_providers=CompositeConfig_OidcProviders(),
        ),
        secret_provider=AdapterConfig_SecretProvider(
            secret_provider_type="local",
            driver=DriverConfig_SecretProvider_Local(),
        ),
        jwt_signer=AdapterConfig_JwtSigner(
            signer_type="local",
            driver=DriverConfig_JwtSigner_Local(
                algorithm="HS256",
                secret_key="test-secret-key",
            ),
        ),
    )

    class DummyAuthService:
        def __init__(self, config):
            self.config = config

    with patch.object(auth_main, "load_auth_config", return_value=minimal):
        with patch.object(auth_main, "AuthService", DummyAuthService):
            async with auth_main.lifespan(auth_main.app):
                assert True
