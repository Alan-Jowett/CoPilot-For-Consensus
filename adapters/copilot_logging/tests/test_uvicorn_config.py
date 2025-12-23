# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Uvicorn logging configuration."""

import json
import logging
import logging.config
import time
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

from copilot_logging.uvicorn_config import create_uvicorn_log_config, JSONFormatter


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_basic_message(self):
        """Test formatting a basic log message."""
        formatter = JSONFormatter(logger_name="test-service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        log_entry = json.loads(output)

        assert log_entry["level"] == "INFO"
        assert log_entry["logger"] == "test-service"
        assert log_entry["message"] == "Test message"
        assert "timestamp" in log_entry
        assert log_entry["timestamp"].endswith("Z")

    def test_format_with_different_levels(self):
        """Test formatting messages at different log levels."""
        formatter = JSONFormatter(logger_name="test")

        for level_name, level_value in [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
        ]:
            record = logging.LogRecord(
                name="test",
                level=level_value,
                pathname="",
                lineno=0,
                msg=f"{level_name} message",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            log_entry = json.loads(output)

            assert log_entry["level"] == level_name
            assert log_entry["message"] == f"{level_name} message"

    def test_format_with_custom_logger_name(self):
        """Test that custom logger name is used."""
        formatter = JSONFormatter(logger_name="custom-service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        log_entry = json.loads(output)

        assert log_entry["logger"] == "custom-service"

    def test_format_with_extra_fields(self):
        """Test that extra fields from logging calls are included."""
        formatter = JSONFormatter(logger_name="test-service")

        # Create a logger and add extra fields via logging call
        logger = logging.getLogger("test-extra")
        logger.handlers = []
        handler = logging.StreamHandler(StringIO())
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Create a record with extra fields
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add custom fields to the record
        record.user_id = 123
        record.request_id = "abc-456"

        output = formatter.format(record)
        log_entry = json.loads(output)

        assert log_entry["message"] == "Test message"
        assert "extra" in log_entry
        assert log_entry["extra"]["user_id"] == 123
        assert log_entry["extra"]["request_id"] == "abc-456"

    def test_format_uses_record_created_timestamp(self):
        """Test that formatter uses record.created for accurate timestamps."""
        formatter = JSONFormatter(logger_name="test-service")

        # Create a record with a known created timestamp
        test_time = time.time()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.created = test_time

        output = formatter.format(record)
        log_entry = json.loads(output)

        # Verify the timestamp is based on record.created
        expected_time = datetime.fromtimestamp(test_time, tz=timezone.utc)
        expected_timestamp = expected_time.isoformat().replace("+00:00", "Z")

        assert log_entry["timestamp"] == expected_timestamp


class TestCreateUvicornLogConfig:
    """Tests for create_uvicorn_log_config."""

    def test_basic_config_structure(self):
        """Test that config has the required structure."""
        config = create_uvicorn_log_config("test-service", "INFO")

        assert "version" in config
        assert config["version"] == 1
        assert "disable_existing_loggers" in config
        assert config["disable_existing_loggers"] is False
        assert "formatters" in config
        assert "handlers" in config
        assert "loggers" in config

    def test_formatters_configuration(self):
        """Test that formatters are configured correctly."""
        config = create_uvicorn_log_config("test-service", "INFO")

        assert "json" in config["formatters"]
        formatter_config = config["formatters"]["json"]
        assert "logger_name" in formatter_config
        assert formatter_config["logger_name"] == "test-service"

    def test_handlers_configuration(self):
        """Test that handlers are configured correctly."""
        config = create_uvicorn_log_config("test-service", "INFO")

        assert "console" in config["handlers"]
        handler_config = config["handlers"]["console"]
        assert handler_config["class"] == "logging.StreamHandler"
        assert handler_config["formatter"] == "json"
        assert handler_config["stream"] == "ext://sys.stdout"

    def test_loggers_configuration(self):
        """Test that loggers are configured correctly."""
        config = create_uvicorn_log_config("test-service", "INFO")

        # Check uvicorn logger
        assert "uvicorn" in config["loggers"]
        uvicorn_logger = config["loggers"]["uvicorn"]
        assert uvicorn_logger["handlers"] == ["console"]
        assert uvicorn_logger["level"] == "INFO"
        assert uvicorn_logger["propagate"] is False

        # Check uvicorn.error logger
        assert "uvicorn.error" in config["loggers"]
        error_logger = config["loggers"]["uvicorn.error"]
        assert error_logger["level"] == "INFO"

        # Check uvicorn.access logger - should be DEBUG for health checks
        assert "uvicorn.access" in config["loggers"]
        access_logger = config["loggers"]["uvicorn.access"]
        assert access_logger["level"] == "DEBUG"
        assert access_logger["handlers"] == ["console"]
        assert access_logger["propagate"] is False

    def test_access_log_level_is_debug(self):
        """Test that access logs are set to DEBUG level regardless of service log level."""
        for log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            config = create_uvicorn_log_config("test-service", log_level)

            # Access logs should always be DEBUG
            assert config["loggers"]["uvicorn.access"]["level"] == "DEBUG"

            # Other loggers should respect the configured level
            assert config["loggers"]["uvicorn"]["level"] == log_level
            assert config["loggers"]["uvicorn.error"]["level"] == log_level

    def test_different_service_names(self):
        """Test that service name is correctly set in formatter."""
        service_names = ["parsing", "chunking", "embedding", "orchestrator"]

        for service_name in service_names:
            config = create_uvicorn_log_config(service_name, "INFO")
            assert config["formatters"]["json"]["logger_name"] == service_name

    def test_integration_with_logging_system(self):
        """Test that the config can be used with Python logging system."""
        config = create_uvicorn_log_config("test-service", "INFO")

        # This should not raise an error
        logging.config.dictConfig(config)

        # Test that the logger works
        logger = logging.getLogger("uvicorn.access")
        assert logger.level == logging.DEBUG


class TestJSONFormatterIntegration:
    """Integration tests for JSONFormatter with logging system."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_json_output_format(self, mock_stdout):
        """Test that JSON formatter produces valid JSON output."""
        # Configure logging with JSON formatter
        handler = logging.StreamHandler(mock_stdout)
        formatter = JSONFormatter(logger_name="test")
        handler.setFormatter(formatter)

        logger = logging.getLogger("test-integration")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Log a message
        logger.info("Health check received")

        # Parse output
        output = mock_stdout.getvalue().strip()
        log_entry = json.loads(output)

        # Verify structure
        assert log_entry["level"] == "INFO"
        assert log_entry["logger"] == "test"
        assert log_entry["message"] == "Health check received"
        assert "timestamp" in log_entry

    @patch('sys.stdout', new_callable=StringIO)
    def test_debug_level_messages(self, mock_stdout):
        """Test that DEBUG level messages are formatted correctly."""
        handler = logging.StreamHandler(mock_stdout)
        formatter = JSONFormatter(logger_name="uvicorn.access")
        handler.setFormatter(formatter)

        logger = logging.getLogger("test-debug")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Log a DEBUG message
        logger.debug('GET /health HTTP/1.1" 200 OK')

        # Parse output
        output = mock_stdout.getvalue().strip()
        log_entry = json.loads(output)

        # Verify DEBUG level
        assert log_entry["level"] == "DEBUG"
        assert log_entry["logger"] == "uvicorn.access"
