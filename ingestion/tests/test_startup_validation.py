# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for startup dependency validation in ingestion service."""

import os
import sys
from unittest.mock import Mock, patch

import pytest

from copilot_config.generated.services.ingestion import ServiceConfig_Ingestion, ServiceSettings_Ingestion
from copilot_config.generated.adapters.archive_store import AdapterConfig_ArchiveStore, DriverConfig_ArchiveStore_Local
from copilot_config.generated.adapters.document_store import AdapterConfig_DocumentStore, DriverConfig_DocumentStore_Inmemory
from copilot_config.generated.adapters.error_reporter import AdapterConfig_ErrorReporter, DriverConfig_ErrorReporter_Silent
from copilot_config.generated.adapters.logger import AdapterConfig_Logger, DriverConfig_Logger_Silent
from copilot_config.generated.adapters.message_bus import AdapterConfig_MessageBus, DriverConfig_MessageBus_Noop, DriverConfig_MessageBus_Rabbitmq
from copilot_config.generated.adapters.metrics import AdapterConfig_Metrics, DriverConfig_Metrics_Noop
from copilot_config.generated.adapters.secret_provider import AdapterConfig_SecretProvider, DriverConfig_SecretProvider_Local

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_service_config(
    *,
    message_bus_driver: str = "rabbitmq",
    document_store_driver: str = "mongodb",
    archive_store_driver: str = "local",
    http_port: int = 8086,
) -> ServiceConfig_Ingestion:
    if message_bus_driver == "noop":
        message_bus = AdapterConfig_MessageBus(
            message_bus_type="noop",
            driver=DriverConfig_MessageBus_Noop(),
        )
    else:
        message_bus = AdapterConfig_MessageBus(
            message_bus_type="rabbitmq",
            driver=DriverConfig_MessageBus_Rabbitmq(
                rabbitmq_host="localhost",
                rabbitmq_port=5672,
                rabbitmq_username="guest",
                rabbitmq_password="guest",
            ),
        )

    # For startup validation we can use inmemory document store.
    document_store = AdapterConfig_DocumentStore(
        doc_store_type="inmemory",
        driver=DriverConfig_DocumentStore_Inmemory(),
    )

    archive_store = AdapterConfig_ArchiveStore(
        archive_store_type="local",
        driver=DriverConfig_ArchiveStore_Local(archive_base_path="/tmp/archives"),
    )

    return ServiceConfig_Ingestion(
        service_settings=ServiceSettings_Ingestion(http_port=http_port),
        archive_store=archive_store,
        document_store=document_store,
        error_reporter=AdapterConfig_ErrorReporter(
            error_reporter_type="silent",
            driver=DriverConfig_ErrorReporter_Silent(),
        ),
        logger=AdapterConfig_Logger(
            logger_type="silent",
            driver=DriverConfig_Logger_Silent(level="INFO", name="ingestion-test"),
        ),
        message_bus=message_bus,
        metrics=AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop()),
        secret_provider=AdapterConfig_SecretProvider(
            secret_provider_type="local",
            driver=DriverConfig_SecretProvider_Local(base_path="/run/secrets"),
        ),
    )


def test_main_imports_successfully():
    """Test that main.py imports successfully without errors."""
    import main as ingestion_main
    assert ingestion_main is not None


def test_service_fails_when_publisher_connection_fails():
    """Test that service fails fast when publisher cannot connect."""
    with patch("main.get_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            with patch("main.create_logger") as mock_create_logger:
                with patch("main.create_metrics_collector") as mock_create_metrics:
                    with patch("main.create_error_reporter") as mock_create_error_reporter:
                        with patch("main.create_document_store"):
                            with patch("main.create_archive_store"):
                                with patch("threading.Thread.start"):
                                    with patch("uvicorn.run"):
                                        mock_config.return_value = _make_service_config(message_bus_driver="rabbitmq")

                                        mock_logger = Mock()
                                        mock_create_logger.return_value = mock_logger
                                        mock_create_metrics.return_value = Mock()
                                        mock_create_error_reporter.return_value = Mock()

                                        # Setup mock publisher that fails to connect
                                        mock_publisher = Mock()
                                        mock_publisher.connect = Mock(side_effect=ConnectionError("Connection failed"))
                                        mock_create_publisher.return_value = mock_publisher

                                        # Import main after setting up mocks
                                        import main as ingestion_main

                                        # Service should raise ConnectionError and exit
                                        with pytest.raises(SystemExit) as exc_info:
                                            ingestion_main.main()

                                        # Should exit with code 1 (error)
                                        assert exc_info.value.code == 1


def test_service_fails_when_document_store_connection_fails():
    """Test that service fails fast when document store cannot connect."""
    from copilot_storage import DocumentStoreConnectionError

    with patch("main.get_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            with patch("main.create_logger") as mock_create_logger:
                with patch("main.create_metrics_collector") as mock_create_metrics:
                    with patch("main.create_error_reporter") as mock_create_error_reporter:
                        with patch("main.create_document_store") as mock_create_store:
                            with patch("main.create_archive_store"):
                                with patch("threading.Thread.start"):
                                    with patch("uvicorn.run"):
                                        mock_config.return_value = _make_service_config()

                                        mock_logger = Mock()
                                        mock_create_logger.return_value = mock_logger
                                        mock_create_metrics.return_value = Mock()
                                        mock_create_error_reporter.return_value = Mock()

                                        # Setup mock publisher that connects successfully
                                        mock_publisher = Mock()
                                        mock_publisher.connect = Mock(return_value=None)
                                        mock_create_publisher.return_value = mock_publisher

                                        # Setup mock document store that fails to connect
                                        mock_store = Mock()
                                        mock_store.connect = Mock(side_effect=DocumentStoreConnectionError("Connection failed"))
                                        mock_create_store.return_value = mock_store

                                        # Import main after setting up mocks
                                        import main as ingestion_main

                                        # Service should raise and exit
                                        with pytest.raises(SystemExit) as exc_info:
                                            ingestion_main.main()

                                        # Should exit with code 1 (error)
                                        assert exc_info.value.code == 1
