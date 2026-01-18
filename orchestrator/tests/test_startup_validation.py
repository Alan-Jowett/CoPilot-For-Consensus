# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for startup dependency validation in orchestrator service."""

import os
import sys
from unittest.mock import Mock, patch

import pytest
from copilot_config.generated.adapters.consensus_detector import (
    AdapterConfig_ConsensusDetector,
    DriverConfig_ConsensusDetector_Mock,
)
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_Inmemory,
    DriverConfig_DocumentStore_Mongodb,
)
from copilot_config.generated.adapters.embedding_backend import (
    AdapterConfig_EmbeddingBackend,
    DriverConfig_EmbeddingBackend_Mock,
)
from copilot_config.generated.adapters.error_reporter import (
    AdapterConfig_ErrorReporter,
    DriverConfig_ErrorReporter_Silent,
)
from copilot_config.generated.adapters.logger import (
    AdapterConfig_Logger,
    DriverConfig_Logger_Silent,
)
from copilot_config.generated.adapters.message_bus import (
    AdapterConfig_MessageBus,
    DriverConfig_MessageBus_Noop,
    DriverConfig_MessageBus_Rabbitmq,
)
from copilot_config.generated.adapters.metrics import (
    AdapterConfig_Metrics,
    DriverConfig_Metrics_Noop,
)
from copilot_config.generated.adapters.secret_provider import (
    AdapterConfig_SecretProvider,
    DriverConfig_SecretProvider_Local,
)
from copilot_config.generated.adapters.vector_store import (
    AdapterConfig_VectorStore,
    DriverConfig_VectorStore_Inmemory,
)
from copilot_config.generated.services.orchestrator import (
    ServiceConfig_Orchestrator,
    ServiceSettings_Orchestrator,
)

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_service_config(
    *,
    message_bus_driver: str = "rabbitmq",
    document_store_driver: str = "mongodb",
    http_port: int = 8083,
) -> ServiceConfig_Orchestrator:
    return ServiceConfig_Orchestrator(
        service_settings=ServiceSettings_Orchestrator(http_port=http_port),
        consensus_detector=AdapterConfig_ConsensusDetector(
            consensus_detector_type="mock",
            driver=DriverConfig_ConsensusDetector_Mock(),
        ),
        embedding_backend=AdapterConfig_EmbeddingBackend(
            embedding_backend_type="mock",
            driver=DriverConfig_EmbeddingBackend_Mock(),
        ),
        vector_store=AdapterConfig_VectorStore(
            vector_store_type="inmemory",
            driver=DriverConfig_VectorStore_Inmemory(),
        ),
        secret_provider=AdapterConfig_SecretProvider(
            secret_provider_type="local",
            driver=DriverConfig_SecretProvider_Local(),
        ),
        error_reporter=AdapterConfig_ErrorReporter(
            error_reporter_type="silent",
            driver=DriverConfig_ErrorReporter_Silent(),
        ),
        logger=AdapterConfig_Logger(
            logger_type="silent",
            driver=DriverConfig_Logger_Silent(level="INFO", name="orchestrator-test"),
        ),
        message_bus=AdapterConfig_MessageBus(
            message_bus_type="rabbitmq" if message_bus_driver == "rabbitmq" else "noop",
            driver=(
                DriverConfig_MessageBus_Rabbitmq(
                    rabbitmq_host="localhost",
                    rabbitmq_port=5672,
                    rabbitmq_username="guest",
                    rabbitmq_password="guest",
                )
                if message_bus_driver == "rabbitmq"
                else DriverConfig_MessageBus_Noop()
            ),
        ),
        document_store=AdapterConfig_DocumentStore(
            doc_store_type="mongodb" if document_store_driver == "mongodb" else "inmemory",
            driver=(
                DriverConfig_DocumentStore_Mongodb(
                    host="localhost",
                    port=27017,
                    database="test_db",
                    username=None,
                    password=None,
                )
                if document_store_driver == "mongodb"
                else DriverConfig_DocumentStore_Inmemory()
            ),
        ),
        metrics=AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop()),
    )


def test_main_imports_successfully():
    """Test that main.py imports successfully without errors."""
    with patch("main.get_config"):
        with patch("main.create_publisher"):
            with patch("main.create_subscriber"):
                with patch("main.create_document_store"):
                    with patch("threading.Thread.start"):
                        with patch("uvicorn.run"):
                            # This will catch ImportError if any imports fail
                            import main as orchestrator_main

                            assert orchestrator_main is not None


def test_service_fails_when_publisher_connection_fails():
    """Test that service fails fast when publisher cannot connect."""
    with patch("main.get_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            mock_config.return_value = _make_service_config(message_bus_driver="rabbitmq")

            # Setup mock publisher that fails to connect
            mock_publisher = Mock()
            mock_publisher.connect = Mock(side_effect=ConnectionError("Connection failed"))
            mock_create_publisher.return_value = mock_publisher

            # Import main after setting up mocks
            import main as orchestrator_main

            # Service should raise ConnectionError and exit
            with pytest.raises(SystemExit) as exc_info:
                orchestrator_main.main()

            # Should exit with code 1 (error)
            assert exc_info.value.code == 1


def test_service_fails_when_subscriber_connection_fails():
    """Test that service fails fast when subscriber cannot connect."""
    with patch("main.get_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            with patch("main.create_subscriber") as mock_create_subscriber:
                mock_config.return_value = _make_service_config(message_bus_driver="rabbitmq")

                # Setup mock publisher that connects successfully
                mock_publisher = Mock()
                mock_publisher.connect = Mock(return_value=None)
                mock_create_publisher.return_value = mock_publisher

                # Setup mock subscriber that fails to connect
                mock_subscriber = Mock()
                mock_subscriber.connect = Mock(side_effect=ConnectionError("Connection failed"))
                mock_create_subscriber.return_value = mock_subscriber

                # Import main after setting up mocks
                import main as orchestrator_main

                # Service should raise ConnectionError and exit
                with pytest.raises(SystemExit) as exc_info:
                    orchestrator_main.main()

                # Should exit with code 1 (error)
                assert exc_info.value.code == 1


def test_service_fails_when_document_store_connection_fails():
    """Test that service fails fast when document store cannot connect."""
    with patch("main.get_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            with patch("main.create_subscriber") as mock_create_subscriber:
                with patch("main.create_document_store") as mock_create_store:
                    with patch("threading.Thread.start"):
                        with patch("uvicorn.run"):
                            mock_config.return_value = _make_service_config()

                            # Setup mocks that connect successfully
                            mock_publisher = Mock()
                            mock_publisher.connect = Mock(return_value=None)
                            mock_create_publisher.return_value = mock_publisher

                            mock_subscriber = Mock()
                            mock_subscriber.connect = Mock(return_value=None)
                            mock_create_subscriber.return_value = mock_subscriber

                            # Setup mock document store that fails to connect
                            mock_store = Mock()
                            mock_store.connect = Mock(side_effect=ConnectionError("Connection failed"))
                            mock_create_store.return_value = mock_store

                            # Import main after setting up mocks
                            import main as orchestrator_main

                            # Service should raise ConnectionError and exit
                            with pytest.raises(SystemExit) as exc_info:
                                orchestrator_main.main()

                            # Should exit with code 1 (error)
                            assert exc_info.value.code == 1
