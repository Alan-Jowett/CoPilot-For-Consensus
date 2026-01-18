# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for startup dependency validation in embedding service."""

import os
import sys
from unittest.mock import Mock, patch

import pytest

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
    DriverConfig_ErrorReporter_Console,
)
from copilot_config.generated.adapters.event_retry import (
    AdapterConfig_EventRetry,
    DriverConfig_EventRetry_Default,
)
from copilot_config.generated.adapters.logger import (
    AdapterConfig_Logger,
    DriverConfig_Logger_Stdout,
)
from copilot_config.generated.adapters.message_bus import (
    AdapterConfig_MessageBus,
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
    DriverConfig_VectorStore_Qdrant,
)
from copilot_config.generated.services.embedding import ServiceConfig_Embedding, ServiceSettings_Embedding

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_service_config(
    *,
    message_bus_driver: str = "rabbitmq",
    document_store_driver: str = "mongodb",
    vectorstore_driver: str = "qdrant",
    http_port: int = 8082,
) -> ServiceConfig_Embedding:
    # Use jwt_auth_enabled=False to avoid importing/initializing auth middleware in unit tests.
    return ServiceConfig_Embedding(
        service_settings=ServiceSettings_Embedding(
            http_port=http_port,
            jwt_auth_enabled=False,
        ),
        logger=AdapterConfig_Logger(
            logger_type="stdout",
            driver=DriverConfig_Logger_Stdout(level="INFO", name="embedding"),
        ),
        message_bus=AdapterConfig_MessageBus(
            message_bus_type=message_bus_driver,
            driver=DriverConfig_MessageBus_Rabbitmq(
                rabbitmq_username="guest",
                rabbitmq_password="guest",
                rabbitmq_host="localhost",
                rabbitmq_port=5672,
            ),
        ),
        document_store=AdapterConfig_DocumentStore(
            doc_store_type="inmemory" if document_store_driver == "inmemory" else "mongodb",
            driver=(
                DriverConfig_DocumentStore_Inmemory()
                if document_store_driver == "inmemory"
                else DriverConfig_DocumentStore_Mongodb(host="localhost", port=27017, database="test_db")
            ),
        ),
        vector_store=AdapterConfig_VectorStore(
            vector_store_type="inmemory" if vectorstore_driver == "inmemory" else "qdrant",
            driver=(
                DriverConfig_VectorStore_Inmemory()
                if vectorstore_driver == "inmemory"
                else DriverConfig_VectorStore_Qdrant(host="localhost", port=6333, collection_name="embeddings")
            ),
        ),
        embedding_backend=AdapterConfig_EmbeddingBackend(
            embedding_backend_type="mock",
            driver=DriverConfig_EmbeddingBackend_Mock(dimension=384),
        ),
        metrics=AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop()),
        error_reporter=AdapterConfig_ErrorReporter(
            error_reporter_type="console",
            driver=DriverConfig_ErrorReporter_Console(logger_name="embedding"),
        ),
        event_retry=AdapterConfig_EventRetry(
            event_retry_type="default",
            driver=DriverConfig_EventRetry_Default(),
        ),
        secret_provider=AdapterConfig_SecretProvider(
            secret_provider_type="local",
            driver=DriverConfig_SecretProvider_Local(base_path="/run/secrets"),
        ),
    )


def test_main_imports_successfully():
    """Test that main.py imports successfully without errors."""
    with patch("main.get_config"):
        with patch("main.create_publisher"):
            with patch("main.create_subscriber"):
                with patch("main.create_document_store"):
                    with patch("main.create_vector_store"):
                        with patch("main.create_embedding_provider"):
                            with patch("threading.Thread.start"):
                                with patch("uvicorn.run"):
                                    # This will catch ImportError if any imports fail
                                    import main as embedding_main
                                    assert embedding_main is not None


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
            import main as embedding_main

            # Service should raise ConnectionError and exit
            with pytest.raises(SystemExit) as exc_info:
                embedding_main.main()

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
                import main as embedding_main

                # Service should raise ConnectionError and exit
                with pytest.raises(SystemExit) as exc_info:
                    embedding_main.main()

                # Should exit with code 1 (error)
                assert exc_info.value.code == 1


def test_service_fails_when_document_store_connection_fails():
    """Test that service fails fast when document store cannot connect."""
    with patch("main.get_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            with patch("main.create_subscriber") as mock_create_subscriber:
                with patch("main.create_document_store") as mock_create_store:
                    with patch("main.create_schema_provider"):
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
                            import main as embedding_main

                            # Service should raise ConnectionError and exit
                            with pytest.raises(SystemExit) as exc_info:
                                embedding_main.main()

                            # Should exit with code 1 (error)
                            assert exc_info.value.code == 1
