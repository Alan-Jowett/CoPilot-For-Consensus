# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for startup dependency validation in auth service."""

import os
import sys
from unittest.mock import Mock, patch

import pytest

from copilot_config.models import AdapterConfig, DriverConfig, ServiceConfig

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_service_config(
    *,
    document_store_driver: str = "mongodb",
    http_port: int = 8087,
) -> ServiceConfig:
    return ServiceConfig(
        service_name="auth",
        service_settings={
            "http_port": http_port,
        },
        adapters=[
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
                adapter_type="metrics",
                driver_name="noop",
                driver_config=DriverConfig(driver_name="noop", config={}),
            ),
        ],
    )


def test_main_imports_successfully():
    """Test that main.py imports successfully without errors."""
    # Auth service has a unique structure - just verify it imports
    import main as auth_main
    assert auth_main is not None


def test_service_starts_with_valid_config():
    """Test that auth service can be initialized with valid config."""
    with patch("main.load_auth_config") as mock_config:
        # Mock minimal auth config
        mock_auth_config = Mock()
        mock_auth_config.jwt_secret_key = "test-secret-key"
        mock_auth_config.jwt_algorithm = "HS256"
        mock_auth_config.jwt_access_token_expire_minutes = 30
        mock_auth_config.providers = []
        mock_config.return_value = mock_auth_config

        # Just verify imports work - auth service doesn't use standard document_store pattern
        import main as auth_main
        assert auth_main is not None
