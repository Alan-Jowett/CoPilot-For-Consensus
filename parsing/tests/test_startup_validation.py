# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for startup dependency validation in parsing service."""

import os
import sys
from unittest.mock import Mock, patch

import pytest

from copilot_config.models import AdapterConfig, DriverConfig, ServiceConfig

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_service_config(
    *,
    message_bus_driver: str = "rabbitmq",
    document_store_driver: str = "mongodb",
    archive_store_driver: str = "local",
    http_port: int = 8081,
) -> ServiceConfig:
    return ServiceConfig(
        service_name="parsing",
        service_settings={
            "http_port": http_port,
        },
        adapters=[
            AdapterConfig(
                adapter_type="message_bus",
                driver_name=message_bus_driver,
                driver_config=DriverConfig(
                    driver_name=message_bus_driver,
                    config={
                        "rabbitmq_host": "localhost",
                        "rabbitmq_port": 5672,
                        "rabbitmq_username": "guest",
                        "rabbitmq_password": "guest",
                    },
                ),
            ),
            AdapterConfig(
                adapter_type="document_store",
                driver_name=document_store_driver,
                driver_config=DriverConfig(
                    driver_name=document_store_driver,
                    config={
                        "mongodb_host": "localhost",
                        "mongodb_port": 27017,
                        "mongodb_database": "test_db",
                    },
                ),
            ),
            AdapterConfig(
                adapter_type="archive_store",
                driver_name=archive_store_driver,
                driver_config=DriverConfig(
                    driver_name=archive_store_driver,
                    config={"base_path": "/tmp/archives"},
                ),
            ),
            AdapterConfig(
                adapter_type="metrics",
                driver_name="noop",
                driver_config=DriverConfig(driver_name="noop", config={}),
            ),
        ],
    )


def test_main_imports_successfully():
    """Test that main.py imports successfully without errors."""
    with patch("main.load_service_config"):
        with patch("main.create_publisher"):
            with patch("main.create_subscriber"):
                with patch("main.create_document_store"):
                    with patch("main.create_archive_store"):
                        with patch("threading.Thread.start"):
                            with patch("uvicorn.run"):
                                # This will catch ImportError if any imports fail
                                import main as parsing_main
                                assert parsing_main is not None


def test_service_fails_when_publisher_connection_fails():
    """Test that service fails fast when publisher cannot connect."""
    with patch("main.load_service_config") as mock_config:
        with patch("main.create_publisher") as mock_create_publisher:
            mock_config.return_value = _make_service_config(message_bus_driver="rabbitmq")

            # Setup mock publisher that fails to connect
            mock_publisher = Mock()
            mock_publisher.connect = Mock(side_effect=ConnectionError("Connection failed"))
            mock_create_publisher.return_value = mock_publisher

            # Import main after setting up mocks
            import main as parsing_main

            # Service should raise ConnectionError and exit
            with pytest.raises(SystemExit) as exc_info:
                parsing_main.main()

            # Should exit with code 1 (error)
            assert exc_info.value.code == 1


def test_service_fails_when_subscriber_connection_fails():
    """Test that service fails fast when subscriber cannot connect."""
    with patch("main.load_service_config") as mock_config:
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
                import main as parsing_main

                # Service should raise ConnectionError and exit
                with pytest.raises(SystemExit) as exc_info:
                    parsing_main.main()

                # Should exit with code 1 (error)
                assert exc_info.value.code == 1


def test_service_fails_when_document_store_connection_fails():
    """Test that service fails fast when document store cannot connect."""
    with patch("main.load_service_config") as mock_config:
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
                            import main as parsing_main

                            # Service should raise ConnectionError and exit
                            with pytest.raises(SystemExit) as exc_info:
                                parsing_main.main()

                            # Should exit with code 1 (error)
                            assert exc_info.value.code == 1
