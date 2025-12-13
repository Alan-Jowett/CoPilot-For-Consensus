# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for startup dependency validation in chunking service."""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_service_fails_when_publisher_connection_fails():
    """Test that service fails fast when publisher cannot connect."""
    with patch("copilot_config.load_typed_config") as mock_config:
        with patch("copilot_events.create_publisher") as mock_create_publisher:
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
            
            # Setup mock publisher that fails to connect
            mock_publisher = Mock()
            mock_publisher.connect = Mock(return_value=False)
            mock_create_publisher.return_value = mock_publisher
            
            # Import main after setting up mocks
            from chunking import main as chunking_main
            
            # Service should raise ConnectionError and exit
            with pytest.raises(SystemExit) as exc_info:
                chunking_main.main()
            
            # Should exit with code 1 (error)
            assert exc_info.value.code == 1


def test_service_fails_when_subscriber_connection_fails():
    """Test that service fails fast when subscriber cannot connect."""
    with patch("copilot_config.load_typed_config") as mock_config:
        with patch("copilot_events.create_publisher") as mock_create_publisher:
            with patch("copilot_events.create_subscriber") as mock_create_subscriber:
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
                
                # Setup mock subscriber that fails to connect
                mock_subscriber = Mock()
                mock_subscriber.connect = Mock(return_value=False)
                mock_create_subscriber.return_value = mock_subscriber
                
                # Import main after setting up mocks
                from chunking import main as chunking_main
                
                # Service should raise ConnectionError and exit
                with pytest.raises(SystemExit) as exc_info:
                    chunking_main.main()
                
                # Should exit with code 1 (error)
                assert exc_info.value.code == 1


def test_service_fails_when_document_store_connection_fails():
    """Test that service fails fast when document store cannot connect."""
    with patch("copilot_config.load_typed_config") as mock_config:
        with patch("copilot_events.create_publisher") as mock_create_publisher:
            with patch("copilot_events.create_subscriber") as mock_create_subscriber:
                with patch("copilot_storage.create_document_store") as mock_create_store:
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
                    
                    # Setup mock document store that fails to connect
                    mock_store = Mock()
                    mock_store.connect = Mock(return_value=False)
                    mock_create_store.return_value = mock_store
                    
                    # Import main after setting up mocks
                    from chunking import main as chunking_main
                    
                    # Service should raise ConnectionError and exit
                    with pytest.raises(SystemExit) as exc_info:
                        chunking_main.main()
                    
                    # Should exit with code 1 (error)
                    assert exc_info.value.code == 1


def test_service_allows_noop_publisher_failure():
    """Test that service continues when noop publisher fails to connect."""
    with patch("copilot_config.load_typed_config") as mock_config:
        with patch("copilot_events.create_publisher") as mock_create_publisher:
            with patch("copilot_events.create_subscriber") as mock_create_subscriber:
                with patch("copilot_storage.create_document_store") as mock_create_store:
                    with patch("copilot_chunking.create_chunker") as mock_create_chunker:
                        with patch("copilot_metrics.create_metrics_collector") as mock_metrics:
                            with patch("copilot_reporting.create_error_reporter") as mock_reporter:
                                with patch("copilot_schema_validation.FileSchemaProvider") as mock_schema_provider:
                                    with patch("threading.Thread.start"):  # Prevent thread creation
                                        with patch("uvicorn.run"):  # Prevent uvicorn from blocking
                                            # Setup mock config with noop message bus
                                            config = Mock()
                                            config.message_bus_type = "noop"
                                            config.message_bus_host = "localhost"
                                            config.message_bus_port = 5672
                                            config.message_bus_user = "guest"
                                            config.message_bus_password = "guest"
                                            config.doc_store_type = "inmemory"
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
                                            
                                            # Setup mock publisher that fails to connect (but is noop)
                                            mock_publisher = Mock()
                                            mock_publisher.connect = Mock(return_value=False)
                                            mock_create_publisher.return_value = mock_publisher
                                            
                                            # Setup mock subscriber that connects successfully
                                            mock_subscriber = Mock()
                                            mock_subscriber.connect = Mock(return_value=True)
                                            mock_create_subscriber.return_value = mock_subscriber
                                            
                                            # Setup mock document store that connects successfully
                                            mock_store = Mock()
                                            mock_store.connect = Mock(return_value=True)
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
                                            from chunking import main as chunking_main
                                            
                                            # Service should complete without raising SystemExit with error code
                                            # Note: uvicorn.run is mocked so it won't block
                                            try:
                                                chunking_main.main()
                                                # Success - service started without error
                                            except SystemExit as e:
                                                # Only fail if exit code is non-zero
                                                if e.code != 0:
                                                    pytest.fail(f"Service should not fail with noop publisher, but got exit code {e.code}")


def test_service_fails_when_schema_missing():
    """Test that service fails fast when required schemas cannot be loaded."""
    with patch("copilot_config.load_typed_config") as mock_config:
        with patch("copilot_events.create_publisher") as mock_create_publisher:
            with patch("copilot_events.create_subscriber") as mock_create_subscriber:
                with patch("copilot_storage.create_document_store") as mock_create_store:
                    with patch("copilot_schema_validation.FileSchemaProvider") as mock_schema_provider:
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
                        from chunking import main as chunking_main
                        
                        # Service should raise RuntimeError and exit
                        with pytest.raises(SystemExit) as exc_info:
                            chunking_main.main()
                        
                        # Should exit with code 1 (error)
                        assert exc_info.value.code == 1


def test_service_fails_when_doc_store_lacks_write_permission():
    """Test that service fails fast when document store lacks write permission."""
    with patch("copilot_config.load_typed_config") as mock_config:
        with patch("copilot_events.create_publisher") as mock_create_publisher:
            with patch("copilot_events.create_subscriber") as mock_create_subscriber:
                with patch("copilot_storage.create_document_store") as mock_create_store:
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
                    from chunking import main as chunking_main
                    
                    # Service should raise PermissionError and exit
                    with pytest.raises(SystemExit) as exc_info:
                        chunking_main.main()
                    
                    # Should exit with code 1 (error)
                    assert exc_info.value.code == 1
