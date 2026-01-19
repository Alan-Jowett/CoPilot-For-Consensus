# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for runtime_loader module."""

import os

import pytest
from copilot_config.runtime_loader import get_config


def test_get_config_ingestion_basic(monkeypatch):
    """Test basic typed config loading for ingestion service."""
    # Set up minimal environment
    monkeypatch.setenv("LOG_TYPE", "stdout")
    monkeypatch.setenv("METRICS_TYPE", "noop")
    monkeypatch.setenv("MESSAGE_BUS_TYPE", "noop")
    monkeypatch.setenv("DOCUMENT_STORE_TYPE", "inmemory")
    monkeypatch.setenv("ERROR_REPORTER_TYPE", "silent")
    monkeypatch.setenv("ARCHIVE_STORE_TYPE", "local")
    monkeypatch.setenv("SECRET_PROVIDER_TYPE", "local")

    # Load config
    config = get_config("ingestion")

    # Verify service settings have defaults
    assert config.service_settings is not None
    assert config.service_settings.batch_size == 100
    assert config.service_settings.http_port == 8000

    # Verify adapters are loaded
    assert config.logger is not None
    assert config.logger.logger_type == "stdout"

    assert config.metrics is not None
    assert config.metrics.metrics_type == "noop"

    assert config.message_bus is not None
    assert config.message_bus.message_bus_type == "noop"

    assert config.document_store is not None
    assert config.document_store.doc_store_type == "inmemory"


def test_get_config_with_custom_settings(monkeypatch):
    """Test config loading with custom environment settings."""
    # Set up environment with custom values
    monkeypatch.setenv("INGESTION_BATCH_SIZE", "200")
    monkeypatch.setenv("INGESTION_HTTP_PORT", "9000")
    monkeypatch.setenv("INGESTION_ENABLE_INCREMENTAL", "false")

    monkeypatch.setenv("LOG_TYPE", "stdout")
    monkeypatch.setenv("METRICS_TYPE", "prometheus")

    monkeypatch.setenv("MESSAGE_BUS_TYPE", "noop")
    monkeypatch.setenv("DOCUMENT_STORE_TYPE", "inmemory")
    monkeypatch.setenv("ERROR_REPORTER_TYPE", "silent")
    monkeypatch.setenv("ARCHIVE_STORE_TYPE", "local")
    monkeypatch.setenv("SECRET_PROVIDER_TYPE", "local")

    # Load config
    config = get_config("ingestion")

    # Verify custom settings
    assert config.service_settings.batch_size == 200
    assert config.service_settings.http_port == 9000
    assert config.service_settings.enable_incremental is False

    # Verify adapter is loaded (prometheus driver doesn't have env_var for namespace)
    assert config.metrics.metrics_type == "prometheus"
    # Namespace will be the default since no env_var is defined in schema
    assert config.metrics.driver.namespace == "copilot"


def test_get_config_pushgateway_driver(monkeypatch):
    """Test config loading with pushgateway metrics driver."""
    # Set up environment
    monkeypatch.setenv("LOG_TYPE", "stdout")
    monkeypatch.setenv("METRICS_TYPE", "pushgateway")
    monkeypatch.setenv("PUSHGATEWAY_GATEWAY", "pushgateway:9091")
    monkeypatch.setenv("PUSHGATEWAY_JOB", "ingestion")

    monkeypatch.setenv("MESSAGE_BUS_TYPE", "noop")
    monkeypatch.setenv("DOCUMENT_STORE_TYPE", "inmemory")
    monkeypatch.setenv("ERROR_REPORTER_TYPE", "silent")
    monkeypatch.setenv("ARCHIVE_STORE_TYPE", "local")
    monkeypatch.setenv("SECRET_PROVIDER_TYPE", "local")

    # Load config
    config = get_config("ingestion")

    # Verify pushgateway driver
    assert config.metrics.metrics_type == "pushgateway"
    assert config.metrics.driver.gateway == "pushgateway:9091"
    assert config.metrics.driver.job == "ingestion"


def test_get_config_missing_required_discriminant(monkeypatch):
    """Test that missing required discriminant raises error."""
    # Set up environment without LOG_TYPE (required)
    monkeypatch.delenv("LOG_TYPE", raising=False)
    monkeypatch.setenv("METRICS_TYPE", "noop")
    monkeypatch.setenv("MESSAGE_BUS_TYPE", "noop")
    monkeypatch.setenv("DOCUMENT_STORE_TYPE", "inmemory")
    monkeypatch.setenv("ERROR_REPORTER_TYPE", "silent")
    monkeypatch.setenv("ARCHIVE_STORE_TYPE", "local")
    monkeypatch.setenv("SECRET_PROVIDER_TYPE", "local")

    # Should raise error for missing required adapter
    with pytest.raises(ValueError, match="Adapter logger requires discriminant configuration"):
        get_config("ingestion")


def test_get_config_invalid_service():
    """Test that invalid service name raises error."""
    with pytest.raises(ImportError, match="Generated configuration module not found"):
        get_config("nonexistent_service")


def test_get_config_type_annotations():
    """Test that returned config has proper types."""
    os.environ.setdefault("LOG_TYPE", "stdout")
    os.environ.setdefault("METRICS_TYPE", "noop")
    os.environ.setdefault("MESSAGE_BUS_TYPE", "noop")
    os.environ.setdefault("DOCUMENT_STORE_TYPE", "inmemory")
    os.environ.setdefault("ERROR_REPORTER_TYPE", "silent")
    os.environ.setdefault("ARCHIVE_STORE_TYPE", "local")
    os.environ.setdefault("SECRET_PROVIDER_TYPE", "local")

    config = get_config("ingestion")

    # Verify types are correct
    assert isinstance(config.service_settings.batch_size, int)
    assert isinstance(config.service_settings.http_port, int)
    assert isinstance(config.service_settings.enable_incremental, bool)
    assert isinstance(config.service_settings.http_host, str)


def test_get_config_auth_composite_oidc_providers(monkeypatch, tmp_path):
    """Ensure auth config loads composite oidc_providers into typed dataclasses."""
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()

    # JWT signer keys (required for local RS256)
    (secrets_dir / "jwt_private_key").write_text("PRIVATE_KEY")
    (secrets_dir / "jwt_public_key").write_text("PUBLIC_KEY")

    # OIDC provider secrets (composite adapter)
    (secrets_dir / "github_oauth_client_id").write_text("github-client-id")
    (secrets_dir / "github_oauth_client_secret").write_text("github-client-secret")

    monkeypatch.setenv("SECRET_PROVIDER_TYPE", "local")
    monkeypatch.setenv("SECRETS_BASE_PATH", str(secrets_dir))

    monkeypatch.setenv("JWT_SIGNER_TYPE", "local")

    # Required adapters for auth
    monkeypatch.setenv("LOG_TYPE", "stdout")
    monkeypatch.setenv("METRICS_TYPE", "noop")
    monkeypatch.setenv("DOCUMENT_STORE_TYPE", "inmemory")
    monkeypatch.setenv("AUTH_ISSUER", "http://issuer.example")

    config = get_config("auth")

    assert config.service_settings.issuer == "http://issuer.example"

    assert config.jwt_signer is not None
    assert config.jwt_signer.signer_type == "local"
    assert config.jwt_signer.driver.private_key == "PRIVATE_KEY"
    assert config.jwt_signer.driver.public_key == "PUBLIC_KEY"

    assert config.oidc_providers is not None
    assert config.oidc_providers.oidc_providers is not None
    assert config.oidc_providers.oidc_providers.github is not None
    assert config.oidc_providers.oidc_providers.github.github_client_id == "github-client-id"
    assert config.oidc_providers.oidc_providers.github.github_client_secret == "github-client-secret"


def test_get_config_auth_hs256_requires_jwt_secret_key(monkeypatch, tmp_path):
    """HS256 requires jwt_secret_key and does not require RSA keys."""
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()

    (secrets_dir / "jwt_secret_key").write_text("HMAC_SECRET")

    monkeypatch.setenv("SECRET_PROVIDER_TYPE", "local")
    monkeypatch.setenv("SECRETS_BASE_PATH", str(secrets_dir))

    monkeypatch.setenv("JWT_SIGNER_TYPE", "local")
    monkeypatch.setenv("AUTH_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_ISSUER", "http://issuer.example")

    # Required adapters for auth
    monkeypatch.setenv("LOG_TYPE", "stdout")
    monkeypatch.setenv("METRICS_TYPE", "noop")
    monkeypatch.setenv("DOCUMENT_STORE_TYPE", "inmemory")

    config = get_config("auth")

    assert config.jwt_signer is not None
    assert config.jwt_signer.signer_type == "local"
    assert config.jwt_signer.driver.algorithm == "HS256"
    assert config.jwt_signer.driver.secret_key == "HMAC_SECRET"
    assert config.jwt_signer.driver.private_key is None
    assert config.jwt_signer.driver.public_key is None


def test_get_config_auth_hs256_missing_jwt_secret_key_raises(monkeypatch, tmp_path):
    """HS256 should fail schema validation when jwt_secret_key is missing."""
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()

    monkeypatch.setenv("SECRET_PROVIDER_TYPE", "local")
    monkeypatch.setenv("SECRETS_BASE_PATH", str(secrets_dir))

    monkeypatch.setenv("JWT_SIGNER_TYPE", "local")
    monkeypatch.setenv("AUTH_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_ISSUER", "http://issuer.example")

    # Required adapters for auth
    monkeypatch.setenv("LOG_TYPE", "stdout")
    monkeypatch.setenv("METRICS_TYPE", "noop")
    monkeypatch.setenv("DOCUMENT_STORE_TYPE", "inmemory")

    with pytest.raises(ValueError, match=r"secret_key parameter is required"):
        get_config("auth")


def test_get_config_parsing_archive_store_azureblob_oneof(monkeypatch):
    """Ensure parsing config can instantiate oneOf-generated driver unions.

    The archive_store azureblob driver is generated as a TypeAlias Union of concrete
    dataclass variants. The runtime loader must pick and instantiate the correct
    variant based on the schema discriminant (AZUREBLOB_AUTH_TYPE).
    """
    from copilot_config.generated.adapters.archive_store import (
        DriverConfig_ArchiveStore_Azureblob_ManagedIdentity,
    )

    monkeypatch.setenv("LOG_TYPE", "stdout")
    monkeypatch.setenv("METRICS_TYPE", "noop")
    monkeypatch.setenv("MESSAGE_BUS_TYPE", "noop")
    monkeypatch.setenv("DOCUMENT_STORE_TYPE", "inmemory")
    monkeypatch.setenv("ERROR_REPORTER_TYPE", "silent")
    monkeypatch.setenv("SECRET_PROVIDER_TYPE", "local")

    # Required adapter for parsing: archive_store
    monkeypatch.setenv("ARCHIVE_STORE_TYPE", "azureblob")
    monkeypatch.setenv("AZUREBLOB_AUTH_TYPE", "managed_identity")
    monkeypatch.setenv("AZUREBLOB_ACCOUNT_NAME", "testaccount")

    config = get_config("parsing")

    assert config.archive_store.archive_store_type == "azureblob"
    assert isinstance(config.archive_store.driver, DriverConfig_ArchiveStore_Azureblob_ManagedIdentity)
