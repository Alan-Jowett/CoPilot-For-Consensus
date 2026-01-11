# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for get_logger and set_default_logger functionality."""

import pytest
from copilot_logging import (
    Logger,
    create_stdout_logger,
    get_logger,
    set_default_logger,
)
from copilot_logging.factory import _logger_registry, _default_logger


@pytest.fixture(autouse=True)
def reset_logger_state():
    """Reset global logger state before each test."""
    import copilot_logging.factory as factory
    factory._logger_registry = {}
    factory._default_logger = None
    yield
    factory._logger_registry = {}
    factory._default_logger = None


def test_get_logger_without_default_creates_fallback():
    """Test that get_logger creates a fallback logger when no default is set."""
    logger = get_logger("test.module")
    assert isinstance(logger, Logger)


def test_get_logger_returns_default_after_set():
    """Test that get_logger returns the default logger after set_default_logger."""
    default = create_stdout_logger(name="default")
    set_default_logger(default)
    
    logger = get_logger("test.module")
    assert logger is default


def test_get_logger_caches_by_name():
    """Test that get_logger caches logger instances by name."""
    default = create_stdout_logger(name="default")
    set_default_logger(default)
    
    logger1 = get_logger("test.module")
    logger2 = get_logger("test.module")
    assert logger1 is logger2


def test_get_logger_different_names_return_same_default():
    """Test that different names still return the same default logger instance."""
    default = create_stdout_logger(name="default")
    set_default_logger(default)
    
    logger1 = get_logger("module.a")
    logger2 = get_logger("module.b")
    assert logger1 is default
    assert logger2 is default


def test_get_logger_without_name_returns_default():
    """Test that get_logger() with no name returns the default logger."""
    default = create_stdout_logger(name="default")
    set_default_logger(default)
    
    logger = get_logger()
    assert logger is default


def test_get_logger_without_name_creates_fallback():
    """Test that get_logger() with no name and no default creates fallback."""
    logger = get_logger()
    assert isinstance(logger, Logger)


def test_set_default_logger_updates_global():
    """Test that set_default_logger updates the global default."""
    logger1 = create_stdout_logger(name="logger1")
    logger2 = create_stdout_logger(name="logger2")
    
    set_default_logger(logger1)
    assert get_logger("test") is logger1
    
    set_default_logger(logger2)
    assert get_logger("test") is logger2


def test_get_logger_usage_pattern():
    """Test the intended usage pattern: set default in main, get in modules."""
    # Simulate main.py setting up the logger
    main_logger = create_stdout_logger(level="INFO", name="my-service")
    set_default_logger(main_logger)
    
    # Simulate module importing and using get_logger
    module_logger = get_logger(__name__)
    assert isinstance(module_logger, Logger)
    assert module_logger is main_logger
    
    # Verify it works for structured logging
    module_logger.info("Test message", key="value")  # Should not raise
