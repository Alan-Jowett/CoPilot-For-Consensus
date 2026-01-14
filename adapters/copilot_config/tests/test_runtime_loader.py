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

    config = get_config("ingestion")

    # Verify types are correct
    assert isinstance(config.service_settings.batch_size, int)
    assert isinstance(config.service_settings.http_port, int)
    assert isinstance(config.service_settings.enable_incremental, bool)
    assert isinstance(config.service_settings.http_host, str)
