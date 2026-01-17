# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration for auth service tests."""

import os
import shutil
import sys
import tempfile
import types
from unittest.mock import MagicMock

import pytest

from copilot_config.generated.adapters.jwt_signer import (
    AdapterConfig_JwtSigner,
    DriverConfig_JwtSigner_Keyvault,
    DriverConfig_JwtSigner_Local,
)


@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Set required environment variables for all auth tests."""
    os.environ["SERVICE_VERSION"] = "0.1.0"

    # Set discriminant types for adapters (use noop/local for tests)
    os.environ["LOG_TYPE"] = "stdout"
    os.environ["METRICS_TYPE"] = "noop"
    os.environ["DOCUMENT_STORE_TYPE"] = "inmemory"
    os.environ["SECRET_PROVIDER_TYPE"] = "local"

    os.environ["OIDC_PROVIDERS_TYPE"] = "multi"
    os.environ["JWT_SIGNER_TYPE"] = "local"

    # Auth service required settings
    os.environ["AUTH_ISSUER"] = "http://localhost:8090"

    secrets_dir = tempfile.mkdtemp(prefix="auth-test-secrets-")
    os.environ["SECRETS_BASE_PATH"] = secrets_dir

    # Provide both RS256 and HS256 key material so individual tests can choose
    # either algorithm without extra setup.
    with open(os.path.join(secrets_dir, "jwt_private_key"), "w", encoding="utf-8") as f:
        f.write("-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----\n")
    with open(os.path.join(secrets_dir, "jwt_public_key"), "w", encoding="utf-8") as f:
        f.write("-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n")
    with open(os.path.join(secrets_dir, "jwt_secret_key"), "w", encoding="utf-8") as f:
        f.write("test-jwt-secret-key")

    yield

    # Clean up environment variables
    os.environ.pop("SERVICE_VERSION", None)
    os.environ.pop("LOG_TYPE", None)
    os.environ.pop("METRICS_TYPE", None)
    os.environ.pop("DOCUMENT_STORE_TYPE", None)
    os.environ.pop("SECRET_PROVIDER_TYPE", None)
    os.environ.pop("AUTH_ISSUER", None)
    secrets_base_path = os.environ.pop("SECRETS_BASE_PATH", None)
    if secrets_base_path:
        shutil.rmtree(secrets_base_path, ignore_errors=True)
    os.environ.pop("OIDC_PROVIDERS_TYPE", None)
    os.environ.pop("JWT_SIGNER_TYPE", None)


@pytest.fixture(autouse=True)
def stub_copilot_jwt_signer(request, monkeypatch):
    """Stub `copilot_jwt_signer` for unit tests.

    AuthService imports `copilot_jwt_signer` at runtime to create signers.
    Most unit tests patch `JWTManager` and don't need real crypto.

    Avoid impacting integration tests by skipping when the `integration`
    marker is present.
    """
    if request.node.get_closest_marker("integration") is not None:
        yield
        return

    module = types.ModuleType("copilot_jwt_signer")
    module.create_jwt_signer = lambda *_args, **_kwargs: MagicMock()
    module.KeyVaultJWTSigner = MagicMock
    monkeypatch.setitem(sys.modules, "copilot_jwt_signer", module)
    yield


@pytest.fixture
def mock_jwt_signer_adapter():
    """Create a JWT signer adapter configuration for local signing."""
    return AdapterConfig_JwtSigner(
        signer_type="local",
        driver=DriverConfig_JwtSigner_Local(
            algorithm="RS256",
            key_id="default",
            private_key="-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----\n",
            public_key="-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n",
            secret_key=None,
        ),
    )


@pytest.fixture
def mock_keyvault_jwt_signer_adapter():
    """Create a JWT signer adapter configuration for Key Vault signing."""
    return AdapterConfig_JwtSigner(
        signer_type="keyvault",
        driver=DriverConfig_JwtSigner_Keyvault(
            key_vault_url="https://test.vault.azure.net/",
            key_name="test-key",
            algorithm="RS256",
            key_id="test-key",
        ),
    )
