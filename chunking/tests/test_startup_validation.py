# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for startup dependency validation in chunking service."""

import os
import sys
from unittest.mock import Mock, patch

import pytest
from copilot_config.generated.adapters.chunker import (
    AdapterConfig_Chunker,
    DriverConfig_Chunker_TokenWindow,
)
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_Inmemory,
    DriverConfig_DocumentStore_Mongodb,
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
from copilot_config.generated.services.chunking import ServiceConfig_Chunking, ServiceSettings_Chunking

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_service_config(
    *,
    message_bus_driver: str = "rabbitmq",
    document_store_driver: str = "mongodb",
    http_port: int = 8000,
    jwt_auth_enabled: bool = True,
    error_reporter_type: str = "console",
) -> ServiceConfig_Chunking:
    if message_bus_driver == "noop":
        message_bus = AdapterConfig_MessageBus(
            message_bus_type="noop",
            driver=DriverConfig_MessageBus_Noop(),
        )
    else:
        message_bus = AdapterConfig_MessageBus(
            message_bus_type="rabbitmq",
            driver=DriverConfig_MessageBus_Rabbitmq(
                rabbitmq_username="guest",
                rabbitmq_password="guest",
                rabbitmq_host="localhost",
                rabbitmq_port=5672,
            ),
        )

    if document_store_driver == "inmemory":
        document_store = AdapterConfig_DocumentStore(
            doc_store_type="inmemory",
            driver=DriverConfig_DocumentStore_Inmemory(),
        )
    else:
        document_store = AdapterConfig_DocumentStore(
            doc_store_type="mongodb",
            driver=DriverConfig_DocumentStore_Mongodb(
                database="test_db",
                host="localhost",
                port=27017,
            ),
        )

    return ServiceConfig_Chunking(
        service_settings=ServiceSettings_Chunking(
            http_port=http_port,
            jwt_auth_enabled=jwt_auth_enabled,
        ),
        message_bus=message_bus,
        document_store=document_store,
        chunker=AdapterConfig_Chunker(
            chunking_strategy="token_window",
            driver=DriverConfig_Chunker_TokenWindow(chunk_size=384, overlap=50),
        ),
        metrics=AdapterConfig_Metrics(
            metrics_type="noop",
            driver=DriverConfig_Metrics_Noop(),
        ),
        logger=AdapterConfig_Logger(
            logger_type="stdout",
            driver=DriverConfig_Logger_Stdout(),
        ),
        error_reporter=AdapterConfig_ErrorReporter(
            error_reporter_type=error_reporter_type,
            driver=DriverConfig_ErrorReporter_Console(),
        ),
        event_retry=AdapterConfig_EventRetry(
            event_retry_type="default",
            driver=DriverConfig_EventRetry_Default(),
        ),
        secret_provider=AdapterConfig_SecretProvider(
            secret_provider_type="local",
            driver=DriverConfig_SecretProvider_Local(),
        ),
    )


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
            import main as chunking_main

            # Service should raise ConnectionError and exit
            with pytest.raises(SystemExit) as exc_info:
                chunking_main.main()

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
                mock_publisher.connect = Mock(return_value=True)
                mock_create_publisher.return_value = mock_publisher

                # Setup mock subscriber that fails to connect
                mock_subscriber = Mock()
                mock_subscriber.connect = Mock(side_effect=ConnectionError("Connection failed"))
                mock_create_subscriber.return_value = mock_subscriber

                # Import main after setting up mocks
                import main as chunking_main

                # Service should raise ConnectionError and exit
                with pytest.raises(SystemExit) as exc_info:
                    chunking_main.main()

                # Should exit with code 1 (error)
                assert exc_info.value.code == 1


def test_service_fails_when_document_store_connection_fails():
    """Test that service fails fast when document store cannot connect."""
    with patch("main.get_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            with patch("main.create_subscriber") as mock_create_subscriber:
                with patch("main.create_document_store") as mock_create_store:
                    with patch("threading.Thread.start"):  # Prevent thread creation
                        with patch("uvicorn.run"):  # Prevent uvicorn from blocking
                            mock_config.return_value = _make_service_config(message_bus_driver="rabbitmq")

                            # Setup mock publisher that connects successfully
                            mock_publisher = Mock()
                            mock_publisher.connect = Mock(return_value=None)
                            mock_create_publisher.return_value = mock_publisher

                            # Setup mock subscriber that connects successfully
                            mock_subscriber = Mock()
                            mock_subscriber.connect = Mock(return_value=None)
                            mock_create_subscriber.return_value = mock_subscriber

                            # Setup mock document store that fails to connect
                            mock_store = Mock()
                            mock_store.connect = Mock(side_effect=ConnectionError("Connection failed"))
                            mock_create_store.return_value = mock_store

                            # Import main after setting up mocks
                            import main as chunking_main

                            # Service should raise ConnectionError and exit
                            with pytest.raises(SystemExit) as exc_info:
                                chunking_main.main()

                            # Should exit with code 1 (error)
                            assert exc_info.value.code == 1


def test_service_allows_noop_publisher_failure():
    """Test that service continues when noop publisher fails to connect."""
    with patch("main.get_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            with patch("main.create_subscriber") as mock_create_subscriber:
                with patch("main.create_document_store") as mock_create_store:
                    with patch("main.create_chunker") as mock_create_chunker:
                        with patch("main.create_metrics_collector") as mock_metrics:
                            with patch("main.create_error_reporter") as mock_reporter:
                                with patch("main.create_schema_provider") as mock_schema_provider:
                                    with patch("threading.Thread.start"):  # Prevent thread creation
                                        with patch("uvicorn.run"):  # Prevent uvicorn from blocking
                                            mock_config.return_value = _make_service_config(
                                                message_bus_driver="noop",
                                                document_store_driver="inmemory",
                                            )

                                            # Setup mock publisher that fails to connect (but is noop)
                                            mock_publisher = Mock()
                                            mock_publisher.connect = Mock(
                                                side_effect=ConnectionError("Connection failed")
                                            )
                                            mock_create_publisher.return_value = mock_publisher

                                            # Setup mock subscriber that connects successfully
                                            mock_subscriber = Mock()
                                            mock_subscriber.connect = Mock(return_value=None)
                                            mock_create_subscriber.return_value = mock_subscriber

                                            # Setup mock document store that connects successfully
                                            mock_store = Mock()
                                            mock_store.connect = Mock(return_value=None)
                                            mock_create_store.return_value = mock_store

                                            # Setup schema provider mock
                                            mock_provider_instance = Mock()
                                            mock_provider_instance.get_schema = Mock(return_value={"type": "object"})
                                            mock_schema_provider.return_value = mock_provider_instance

                                            # Setup other mocks
                                            mock_create_chunker.return_value = Mock()
                                            mock_metrics.return_value = Mock()
                                            mock_reporter.return_value = Mock()

                                            # Import main after setting up mocks
                                            import main as chunking_main

                                            # Service should complete without raising SystemExit with error code
                                            # Note: uvicorn.run is mocked so it won't block
                                            try:
                                                chunking_main.main()
                                                # Success - service started without error
                                            except SystemExit as e:
                                                # Only fail if exit code is non-zero
                                                if e.code != 0:
                                                    pytest.fail(
                                                        f"Service should not fail with noop publisher, but got exit code {e.code}"
                                                    )


@pytest.mark.skip(reason="Schema validation at startup not yet implemented")
def test_service_fails_when_schema_missing():
    """Test that service fails fast when required schemas cannot be loaded."""
    with patch("main.load_service_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            with patch("main.create_subscriber") as mock_create_subscriber:
                with patch("main.create_document_store") as mock_create_store:
                    with patch("main.create_schema_provider") as mock_schema_provider:
                        with patch("threading.Thread.start"):  # Prevent thread creation
                            with patch("uvicorn.run"):  # Prevent uvicorn from blocking
                                # Setup mock config
                                config = Mock()
                                config.message_bus_type = "rabbitmq"
                                config.message_bus_host = "localhost"
                                config.message_bus_port = 5672
                                config.message_bus_user = "guest"
                                config.message_bus_password = "guest"
                                config.doc_store_type = "mongodb"
                                config.doc_store_host = "localhost"
                                config.doc_store_port = 27017
                                config.doc_store_name = "test_db"
                                config.doc_store_user = None
                                config.doc_store_password = None
                                config.chunking_strategy = "token_window"
                                config.chunk_size = 384
                                config.chunk_overlap = 50
                                config.min_chunk_size = 100
                                config.max_chunk_size = 1000
                                config.http_port = 8000
                                mock_config.return_value = config

                                # Setup mock publisher that connects successfully
                                mock_publisher = Mock()
                                mock_publisher.connect = Mock(return_value=True)
                                mock_create_publisher.return_value = mock_publisher

                                # Setup mock subscriber that connects successfully
                                mock_subscriber = Mock()
                                mock_subscriber.connect = Mock(return_value=True)
                                mock_create_subscriber.return_value = mock_subscriber

                                # Setup mock document store that connects successfully
                                mock_store = Mock()
                                mock_store.connect = Mock(return_value=True)
                                mock_store.insert_document = Mock(return_value="test_id")
                                mock_store.get_document = Mock(return_value={"test": True})
                                mock_store.delete_document = Mock(return_value=True)
                                mock_create_store.return_value = mock_store

                                # Setup schema provider that fails to load schemas
                                mock_provider_instance = Mock()
                                mock_provider_instance.get_schema = Mock(return_value=None)  # Simulate missing schema
                                mock_schema_provider.return_value = mock_provider_instance

                                # Import main after setting up mocks
                                import main as chunking_main

                                # Service should raise RuntimeError and exit
                                with pytest.raises(SystemExit) as exc_info:
                                    chunking_main.main()

                                # Should exit with code 1 (error)
                                assert exc_info.value.code == 1


@pytest.mark.skip(reason="Document store write permission validation at startup not yet implemented")
def test_service_fails_when_doc_store_lacks_write_permission():
    """Test that service fails fast when document store lacks write permission."""
    with patch("main.load_service_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            with patch("main.create_subscriber") as mock_create_subscriber:
                with patch("main.create_document_store") as mock_create_store:
                    # Setup mock config
                    config = Mock()
                    config.message_bus_type = "rabbitmq"
                    config.message_bus_host = "localhost"
                    config.message_bus_port = 5672
                    config.message_bus_user = "guest"
                    config.message_bus_password = "guest"
                    config.doc_store_type = "mongodb"
                    config.doc_store_host = "localhost"
                    config.doc_store_port = 27017
                    config.doc_store_name = "test_db"
                    config.doc_store_user = None
                    config.doc_store_password = None
                    config.chunking_strategy = "token_window"
                    config.chunk_size = 384
                    config.chunk_overlap = 50
                    config.min_chunk_size = 100
                    config.max_chunk_size = 1000
                    config.http_port = 8000
                    mock_config.return_value = config

                    # Setup mock publisher that connects successfully
                    mock_publisher = Mock()
                    mock_publisher.connect = Mock(return_value=True)
                    mock_create_publisher.return_value = mock_publisher

                    # Setup mock subscriber that connects successfully
                    mock_subscriber = Mock()
                    mock_subscriber.connect = Mock(return_value=True)
                    mock_create_subscriber.return_value = mock_subscriber

                    # Setup mock document store that connects but can't write
                    mock_store = Mock()
                    mock_store.connect = Mock(return_value=True)
                    mock_store.insert_document = Mock(side_effect=PermissionError("Write not allowed"))
                    mock_create_store.return_value = mock_store

                    # Import main after setting up mocks
                    import main as chunking_main

                    # Service should raise PermissionError and exit
                    with pytest.raises(SystemExit) as exc_info:
                        chunking_main.main()

                    # Should exit with code 1 (error)
                    assert exc_info.value.code == 1
