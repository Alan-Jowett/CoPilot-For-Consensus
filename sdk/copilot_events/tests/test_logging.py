# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for logging abstraction."""

import json
import os
import pytest
from io import StringIO
from unittest.mock import patch

from copilot_logging import (
    create_logger,
    Logger,
    StdoutLogger,
    SilentLogger,
)


class TestLoggerFactory:
    """Tests for create_logger factory function."""

    def test_create_stdout_logger(self):
        """Test creating a stdout logger."""
        logger = create_logger(logger_type="stdout", level="INFO")
        
        assert isinstance(logger, StdoutLogger)
        assert isinstance(logger, Logger)
        assert logger.level == "INFO"

    def test_create_silent_logger(self):
        """Test creating a silent logger."""
        logger = create_logger(logger_type="silent")
        
        assert isinstance(logger, SilentLogger)
        assert isinstance(logger, Logger)

    def test_create_logger_with_name(self):
        """Test creating a logger with a custom name."""
        logger = create_logger(logger_type="stdout", name="test-service")
        
        assert isinstance(logger, StdoutLogger)
        assert logger.name == "test-service"

    def test_create_logger_with_debug_level(self):
        """Test creating a logger with DEBUG level."""
        logger = create_logger(logger_type="stdout", level="DEBUG")
        
        assert isinstance(logger, StdoutLogger)
        assert logger.level == "DEBUG"

    def test_create_unknown_logger_type(self):
        """Test that unknown logger type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown logger_type"):
            create_logger(logger_type="invalid")

    def test_create_logger_from_env(self):
        """Test creating logger from environment variables."""
        with patch.dict(os.environ, {
            "LOG_TYPE": "stdout",
            "LOG_LEVEL": "WARNING",
            "LOG_NAME": "env-service"
        }):
            logger = create_logger()
            
            assert isinstance(logger, StdoutLogger)
            assert logger.level == "WARNING"
            assert logger.name == "env-service"

    def test_create_logger_defaults_to_stdout(self):
        """Test that logger defaults to stdout when not specified."""
        with patch.dict(os.environ, {}, clear=True):
            logger = create_logger()
            
            assert isinstance(logger, StdoutLogger)


class TestSilentLogger:
    """Tests for SilentLogger."""

    def test_initialization(self):
        """Test SilentLogger initialization."""
        logger = SilentLogger(level="DEBUG", name="test-service")
        
        assert logger.level == "DEBUG"
        assert logger.name == "test-service"

    def test_default_values(self):
        """Test default initialization values."""
        logger = SilentLogger()
        
        assert logger.level == "INFO"
        assert logger.name == "copilot"

    def test_info_logging(self):
        """Test logging info-level messages."""
        logger = SilentLogger()
        
        logger.info("Test message")
        
        assert len(logger.logs) == 1
        assert logger.logs[0]["level"] == "INFO"
        assert logger.logs[0]["message"] == "Test message"

    def test_warning_logging(self):
        """Test logging warning-level messages."""
        logger = SilentLogger()
        
        logger.warning("Warning message")
        
        assert len(logger.logs) == 1
        assert logger.logs[0]["level"] == "WARNING"
        assert logger.logs[0]["message"] == "Warning message"

    def test_error_logging(self):
        """Test logging error-level messages."""
        logger = SilentLogger()
        
        logger.error("Error message")
        
        assert len(logger.logs) == 1
        assert logger.logs[0]["level"] == "ERROR"
        assert logger.logs[0]["message"] == "Error message"

    def test_debug_logging(self):
        """Test logging debug-level messages."""
        logger = SilentLogger()
        
        logger.debug("Debug message")
        
        assert len(logger.logs) == 1
        assert logger.logs[0]["level"] == "DEBUG"
        assert logger.logs[0]["message"] == "Debug message"

    def test_logging_with_extra_fields(self):
        """Test logging with additional structured data."""
        logger = SilentLogger()
        
        logger.info("Event occurred", user_id=123, action="login")
        
        assert len(logger.logs) == 1
        assert logger.logs[0]["message"] == "Event occurred"
        assert logger.logs[0]["extra"]["user_id"] == 123
        assert logger.logs[0]["extra"]["action"] == "login"

    def test_multiple_logs(self):
        """Test logging multiple messages."""
        logger = SilentLogger()
        
        logger.info("Message 1")
        logger.warning("Message 2")
        logger.error("Message 3")
        
        assert len(logger.logs) == 3
        assert logger.logs[0]["level"] == "INFO"
        assert logger.logs[1]["level"] == "WARNING"
        assert logger.logs[2]["level"] == "ERROR"

    def test_clear_logs(self):
        """Test clearing stored logs."""
        logger = SilentLogger()
        
        logger.info("Message 1")
        logger.info("Message 2")
        assert len(logger.logs) == 2
        
        logger.clear_logs()
        assert len(logger.logs) == 0

    def test_get_logs_all(self):
        """Test getting all logs."""
        logger = SilentLogger()
        
        logger.info("Info message")
        logger.error("Error message")
        
        logs = logger.get_logs()
        assert len(logs) == 2

    def test_get_logs_filtered_by_level(self):
        """Test getting logs filtered by level."""
        logger = SilentLogger()
        
        logger.info("Info 1")
        logger.warning("Warning 1")
        logger.info("Info 2")
        logger.error("Error 1")
        
        info_logs = logger.get_logs(level="INFO")
        assert len(info_logs) == 2
        assert all(log["level"] == "INFO" for log in info_logs)
        
        warning_logs = logger.get_logs(level="WARNING")
        assert len(warning_logs) == 1
        assert warning_logs[0]["message"] == "Warning 1"

    def test_has_log_message(self):
        """Test checking if a log message exists."""
        logger = SilentLogger()
        
        logger.info("Service started successfully")
        logger.error("Connection failed")
        
        assert logger.has_log("Service started")
        assert logger.has_log("Connection failed")
        assert not logger.has_log("Not logged")

    def test_has_log_with_level_filter(self):
        """Test checking for log message with level filter."""
        logger = SilentLogger()
        
        logger.info("Test message")
        logger.error("Test message")
        
        assert logger.has_log("Test message", level="INFO")
        assert logger.has_log("Test message", level="ERROR")
        assert not logger.has_log("Test message", level="WARNING")


class TestStdoutLogger:
    """Tests for StdoutLogger."""

    def test_initialization(self):
        """Test StdoutLogger initialization."""
        logger = StdoutLogger(level="INFO", name="test-service")
        
        assert logger.level == "INFO"
        assert logger.name == "test-service"

    def test_default_values(self):
        """Test default initialization values."""
        logger = StdoutLogger()
        
        assert logger.level == "INFO"
        assert logger.name == "copilot"

    def test_invalid_log_level(self):
        """Test that invalid log level raises ValueError."""
        with pytest.raises(ValueError, match="Invalid log level"):
            StdoutLogger(level="INVALID")

    @patch('sys.stdout', new_callable=StringIO)
    def test_info_logging_output(self, mock_stdout):
        """Test that info logging produces correct JSON output."""
        logger = StdoutLogger(level="INFO", name="test")
        
        logger.info("Test info message")
        
        output = mock_stdout.getvalue().strip()
        log_entry = json.loads(output)
        
        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Test info message"
        assert log_entry["logger"] == "test"
        assert "timestamp" in log_entry

    @patch('sys.stdout', new_callable=StringIO)
    def test_warning_logging_output(self, mock_stdout):
        """Test that warning logging produces correct JSON output."""
        logger = StdoutLogger(level="INFO", name="test")
        
        logger.warning("Test warning message")
        
        output = mock_stdout.getvalue().strip()
        log_entry = json.loads(output)
        
        assert log_entry["level"] == "WARNING"
        assert log_entry["message"] == "Test warning message"

    @patch('sys.stdout', new_callable=StringIO)
    def test_error_logging_output(self, mock_stdout):
        """Test that error logging produces correct JSON output."""
        logger = StdoutLogger(level="INFO", name="test")
        
        logger.error("Test error message")
        
        output = mock_stdout.getvalue().strip()
        log_entry = json.loads(output)
        
        assert log_entry["level"] == "ERROR"
        assert log_entry["message"] == "Test error message"

    @patch('sys.stdout', new_callable=StringIO)
    def test_debug_logging_output(self, mock_stdout):
        """Test that debug logging produces correct JSON output."""
        logger = StdoutLogger(level="DEBUG", name="test")
        
        logger.debug("Test debug message")
        
        output = mock_stdout.getvalue().strip()
        log_entry = json.loads(output)
        
        assert log_entry["level"] == "DEBUG"
        assert log_entry["message"] == "Test debug message"

    @patch('sys.stdout', new_callable=StringIO)
    def test_logging_with_extra_fields(self, mock_stdout):
        """Test logging with additional structured data."""
        logger = StdoutLogger(level="INFO", name="test")
        
        logger.info("User action", user_id=123, action="login", ip="192.168.1.1")
        
        output = mock_stdout.getvalue().strip()
        log_entry = json.loads(output)
        
        assert log_entry["message"] == "User action"
        assert log_entry["extra"]["user_id"] == 123
        assert log_entry["extra"]["action"] == "login"
        assert log_entry["extra"]["ip"] == "192.168.1.1"

    @patch('sys.stdout', new_callable=StringIO)
    def test_log_level_filtering(self, mock_stdout):
        """Test that logs below the configured level are not output."""
        logger = StdoutLogger(level="WARNING", name="test")
        
        logger.debug("Debug message")  # Should not output
        logger.info("Info message")    # Should not output
        logger.warning("Warning message")  # Should output
        
        output = mock_stdout.getvalue().strip()
        
        # Only one line should be output (the WARNING)
        assert output.count('\n') == 0  # No newlines means one log
        log_entry = json.loads(output)
        assert log_entry["level"] == "WARNING"

    @patch('sys.stdout', new_callable=StringIO)
    def test_multiple_logs(self, mock_stdout):
        """Test multiple log messages."""
        logger = StdoutLogger(level="INFO", name="test")
        
        logger.info("Message 1")
        logger.info("Message 2")
        logger.info("Message 3")
        
        output = mock_stdout.getvalue().strip()
        lines = output.split('\n')
        
        assert len(lines) == 3
        for i, line in enumerate(lines, 1):
            log_entry = json.loads(line)
            assert log_entry["message"] == f"Message {i}"

    @patch('sys.stdout', new_callable=StringIO)
    def test_timestamp_format(self, mock_stdout):
        """Test that timestamp is in ISO format with Z suffix."""
        logger = StdoutLogger(level="INFO", name="test")
        
        logger.info("Test message")
        
        output = mock_stdout.getvalue().strip()
        log_entry = json.loads(output)
        
        # Check timestamp ends with Z and is valid ISO format
        assert log_entry["timestamp"].endswith("Z")
        # Basic format check: YYYY-MM-DDTHH:MM:SS.ffffffZ
        assert len(log_entry["timestamp"]) > 20
