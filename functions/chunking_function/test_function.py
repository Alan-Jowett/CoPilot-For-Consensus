# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Tests for Azure Functions chunking implementation.

These tests validate that the Azure Function wrapper correctly:
1. Initializes the service with proper dependencies
2. Parses Service Bus messages
3. Calls the underlying ChunkingService logic
4. Handles errors appropriately
"""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestChunkingFunction:
    """Test suite for chunking Azure Function."""

    @patch("functions.chunking_function.load_typed_config")
    @patch("functions.chunking_function.create_publisher")
    @patch("functions.chunking_function.create_document_store")
    @patch("functions.chunking_function.create_chunker")
    @patch("functions.chunking_function.create_metrics_collector")
    @patch("functions.chunking_function.create_error_reporter")
    @patch("functions.chunking_function.FileSchemaProvider")
    @patch("functions.chunking_function.ValidatingDocumentStore")
    def test_service_initialization(
        self,
        mock_validating_store,
        mock_schema_provider,
        mock_error_reporter,
        mock_metrics_collector,
        mock_chunker,
        mock_doc_store,
        mock_publisher,
        mock_config,
    ):
        """Test that the service is initialized correctly on first invocation."""
        # Import after mocking
        from functions.chunking_function import get_chunking_service, _chunking_service
        
        # Reset global service
        import functions.chunking_function as func_module
        func_module._chunking_service = None
        
        # Setup mocks
        mock_config_obj = Mock()
        mock_config_obj.message_bus_type = "rabbitmq"
        mock_config_obj.chunking_strategy = "sentence"
        mock_config_obj.chunk_size = 512
        mock_config_obj.chunk_overlap = 50
        mock_config_obj.min_chunk_size = 100
        mock_config_obj.max_chunk_size = 1024
        mock_config.return_value = mock_config_obj
        
        mock_publisher_obj = Mock()
        mock_publisher.return_value = mock_publisher_obj
        
        mock_doc_store_obj = Mock()
        mock_doc_store.return_value = mock_doc_store_obj
        
        # Call service initialization
        service = get_chunking_service()
        
        # Verify service was created
        assert service is not None
        
        # Verify adapters were created
        mock_config.assert_called_once_with("chunking")
        mock_publisher.assert_called_once()
        mock_doc_store.assert_called_once()
        mock_chunker.assert_called_once()
        
        # Verify service is reused on subsequent calls (global caching)
        service2 = get_chunking_service()
        assert service2 is service

    @patch("functions.chunking_function.get_chunking_service")
    def test_function_processes_valid_message(self, mock_get_service):
        """Test that the function processes a valid Service Bus message."""
        from functions.chunking_function import main
        import azure.functions as func
        
        # Setup mock service
        mock_service = Mock()
        mock_service.process_messages = Mock()
        mock_get_service.return_value = mock_service
        
        # Create mock Service Bus message
        event_data = {
            "data": {
                "archive_id": "test-archive",
                "message_doc_ids": ["msg1", "msg2"],
                "message_count": 2,
            }
        }
        message_body = json.dumps(event_data).encode('utf-8')
        
        mock_message = Mock(spec=func.ServiceBusMessage)
        mock_message.get_body.return_value = message_body
        mock_message.message_id = "test-msg-id"
        mock_message.sequence_number = 1
        mock_message.enqueued_time_utc = None
        mock_message.delivery_count = 1
        
        # Call function
        main(mock_message)
        
        # Verify service.process_messages was called with correct data
        mock_service.process_messages.assert_called_once_with(event_data["data"])

    @patch("functions.chunking_function.get_chunking_service")
    def test_function_handles_processing_error(self, mock_get_service):
        """Test that the function re-raises exceptions for Azure Functions retry."""
        from functions.chunking_function import main
        import azure.functions as func
        
        # Setup mock service that raises an error
        mock_service = Mock()
        mock_service.process_messages.side_effect = ValueError("Database connection failed")
        mock_get_service.return_value = mock_service
        
        # Create mock message
        event_data = {"data": {"archive_id": "test", "message_doc_ids": []}}
        message_body = json.dumps(event_data).encode('utf-8')
        
        mock_message = Mock(spec=func.ServiceBusMessage)
        mock_message.get_body.return_value = message_body
        mock_message.message_id = "test-msg-id"
        mock_message.sequence_number = 1
        mock_message.enqueued_time_utc = None
        mock_message.delivery_count = 1
        
        # Verify exception is re-raised (for Azure Functions retry mechanism)
        with pytest.raises(ValueError, match="Database connection failed"):
            main(mock_message)

    @patch("functions.chunking_function.get_chunking_service")
    def test_function_parses_json_message(self, mock_get_service):
        """Test that the function correctly parses JSON from Service Bus message."""
        from functions.chunking_function import main
        import azure.functions as func
        
        # Setup mock service
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        
        # Create message with complex nested data
        event_data = {
            "data": {
                "archive_id": "ietf-archive-2024",
                "message_doc_ids": ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"],
                "message_count": 2,
                "source": "rsync",
            }
        }
        message_body = json.dumps(event_data).encode('utf-8')
        
        mock_message = Mock(spec=func.ServiceBusMessage)
        mock_message.get_body.return_value = message_body
        mock_message.message_id = "test-msg-id"
        mock_message.sequence_number = 1
        mock_message.enqueued_time_utc = None
        mock_message.delivery_count = 1
        
        # Call function
        main(mock_message)
        
        # Verify correct data was passed to service
        call_args = mock_service.process_messages.call_args[0][0]
        assert call_args["archive_id"] == "ietf-archive-2024"
        assert len(call_args["message_doc_ids"]) == 2
        assert call_args["message_count"] == 2
        assert call_args["source"] == "rsync"

    def test_service_reuse_optimization(self):
        """Test that service instance is reused across invocations (warm start)."""
        from functions.chunking_function import get_chunking_service
        import functions.chunking_function as func_module
        
        # Mock the service initialization
        with patch.object(func_module, 'ChunkingService') as mock_service_class:
            # Reset global service
            func_module._chunking_service = None
            
            # Mock dependencies
            with patch("functions.chunking_function.load_typed_config"), \
                 patch("functions.chunking_function.create_publisher"), \
                 patch("functions.chunking_function.create_document_store"), \
                 patch("functions.chunking_function.create_chunker"), \
                 patch("functions.chunking_function.create_metrics_collector"), \
                 patch("functions.chunking_function.create_error_reporter"), \
                 patch("functions.chunking_function.FileSchemaProvider"), \
                 patch("functions.chunking_function.ValidatingDocumentStore"):
                
                # First call - should initialize
                service1 = get_chunking_service()
                assert mock_service_class.call_count == 1
                
                # Second call - should reuse (warm start optimization)
                service2 = get_chunking_service()
                assert mock_service_class.call_count == 1  # Not called again
                assert service2 is service1


class TestFunctionConfiguration:
    """Test Function configuration and bindings."""

    def test_function_json_schema(self):
        """Validate function.json configuration."""
        import json
        from pathlib import Path
        
        function_json_path = Path(__file__).parent.parent / "function.json"
        assert function_json_path.exists(), "function.json not found"
        
        with open(function_json_path) as f:
            config = json.load(f)
        
        # Validate structure
        assert "bindings" in config
        assert len(config["bindings"]) == 1
        
        # Validate Service Bus trigger
        binding = config["bindings"][0]
        assert binding["type"] == "serviceBusTrigger"
        assert binding["direction"] == "in"
        assert binding["queueName"] == "json.parsed"
        assert binding["connection"] == "AzureWebJobsServiceBus"
        
        # Validate retry policy
        assert "retry" in config
        assert config["retry"]["strategy"] == "exponentialBackoff"
        assert config["retry"]["maxRetryCount"] == 5

    def test_host_json_schema(self):
        """Validate host.json configuration."""
        import json
        from pathlib import Path
        
        host_json_path = Path(__file__).parent.parent / "host.json"
        assert host_json_path.exists(), "host.json not found"
        
        with open(host_json_path) as f:
            config = json.load(f)
        
        # Validate version
        assert config["version"] == "2.0"
        
        # Validate Service Bus extension config
        assert "extensions" in config
        assert "serviceBus" in config["extensions"]
        
        sb_config = config["extensions"]["serviceBus"]
        assert sb_config["prefetchCount"] == 100
        assert "messageHandlerOptions" in sb_config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
