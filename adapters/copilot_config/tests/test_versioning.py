# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for schema versioning functionality."""

import json
import os
import pytest

from copilot_config import (
    ConfigSchema,
    ConfigSchemaError,
    TypedConfig,
    load_typed_config,
)
from copilot_config.schema_loader import _is_version_compatible


class TestSchemaVersioning:
    """Tests for schema versioning support."""

    def test_schema_with_version_fields(self):
        """Test creating schema with version fields."""
        schema_data = {
            "service_name": "test-service",
            "schema_version": "1.2.3",
            "min_service_version": "0.5.0",
            "fields": {
                "test_field": {
                    "type": "string",
                    "source": "env",
                    "default": "test",
                },
            },
        }

        schema = ConfigSchema.from_dict(schema_data)

        assert schema.schema_version == "1.2.3"
        assert schema.min_service_version == "0.5.0"

    def test_schema_without_version_fields(self):
        """Test creating schema without version fields (backwards compatible)."""
        schema_data = {
            "service_name": "test-service",
            "fields": {
                "test_field": {
                    "type": "string",
                    "source": "env",
                    "default": "test",
                },
            },
        }

        schema = ConfigSchema.from_dict(schema_data)

        assert schema.schema_version is None
        assert schema.min_service_version is None

    def test_version_compatibility_check(self):
        """Test version compatibility checking."""
        # Same versions should be compatible
        assert _is_version_compatible("1.0.0", "1.0.0")

        # Newer service version should be compatible
        assert _is_version_compatible("1.5.0", "1.0.0")
        assert _is_version_compatible("2.0.0", "1.0.0")

        # Older service version should not be compatible
        assert not _is_version_compatible("0.9.0", "1.0.0")
        assert not _is_version_compatible("1.0.0", "1.5.0")

        # Test patch version compatibility
        assert _is_version_compatible("1.0.1", "1.0.0")
        assert not _is_version_compatible("1.0.0", "1.0.1")

    def test_load_config_with_incompatible_version(self, tmp_path):
        """Test that loading config with incompatible version raises error."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        schema_file = schema_dir / "test-service.json"
        schema_data = {
            "service_name": "test-service",
            "schema_version": "2.0.0",
            "min_service_version": "1.5.0",
            "fields": {
                "test_field": {
                    "type": "string",
                    "source": "env",
                    "default": "test",
                },
            },
        }
        schema_file.write_text(json.dumps(schema_data), encoding="utf-8")

        # Set service version to incompatible version
        os.environ["SERVICE_VERSION"] = "1.0.0"

        try:
            with pytest.raises(ConfigSchemaError, match="not compatible"):
                load_typed_config("test-service", schema_dir=str(schema_dir))
        finally:
            # Clean up
            if "SERVICE_VERSION" in os.environ:
                del os.environ["SERVICE_VERSION"]

    def test_load_config_with_compatible_version(self, tmp_path):
        """Test that loading config with compatible version succeeds."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        schema_file = schema_dir / "test-service.json"
        schema_data = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "min_service_version": "0.5.0",
            "fields": {
                "test_field": {
                    "type": "string",
                    "source": "env",
                    "env_var": "TEST_FIELD",
                    "default": "test",
                },
            },
        }
        schema_file.write_text(json.dumps(schema_data), encoding="utf-8")

        # Set service version to compatible version
        os.environ["SERVICE_VERSION"] = "1.0.0"
        os.environ["TEST_FIELD"] = "test_value"

        try:
            config = load_typed_config("test-service", schema_dir=str(schema_dir))
            assert config.test_field == "test_value"
        finally:
            # Clean up
            if "SERVICE_VERSION" in os.environ:
                del os.environ["SERVICE_VERSION"]
            if "TEST_FIELD" in os.environ:
                del os.environ["TEST_FIELD"]


class TestTypedConfigVersioning:
    """Tests for TypedConfig version exposure."""

    def test_typed_config_exposes_version_info(self, tmp_path):
        """Test that TypedConfig exposes version information."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        schema_file = schema_dir / "test-service.json"
        schema_data = {
            "service_name": "test-service",
            "schema_version": "1.2.3",
            "min_service_version": "0.5.0",
            "fields": {
                "test_field": {
                    "type": "string",
                    "source": "env",
                    "env_var": "TEST_FIELD",
                    "default": "test",
                },
            },
        }
        schema_file.write_text(json.dumps(schema_data), encoding="utf-8")

        os.environ["TEST_FIELD"] = "test_value"
        os.environ["SERVICE_VERSION"] = "1.0.0"

        try:
            config = load_typed_config("test-service", schema_dir=str(schema_dir))

            assert config.get_schema_version() == "1.2.3"
            assert config.get_min_service_version() == "0.5.0"
        finally:
            # Clean up
            if "TEST_FIELD" in os.environ:
                del os.environ["TEST_FIELD"]
            if "SERVICE_VERSION" in os.environ:
                del os.environ["SERVICE_VERSION"]

    def test_typed_config_without_version_info(self):
        """Test TypedConfig without version information."""
        config = TypedConfig({"test": "value"})

        assert config.get_schema_version() is None
        assert config.get_min_service_version() is None
