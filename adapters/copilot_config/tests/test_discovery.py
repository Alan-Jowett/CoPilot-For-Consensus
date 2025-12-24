# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for configuration discovery endpoint."""

import json
import os

import pytest
from copilot_config.discovery import get_configuration_schema_response


class TestDiscoveryEndpoint:
    """Tests for configuration discovery functionality."""

    def test_get_schema_response(self, tmp_path):
        """Test getting schema response for discovery endpoint."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        schema_file = schema_dir / "test-service.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "min_service_version": "0.1.0",
            "metadata": {
                "description": "Test service schema",
            },
            "fields": {
                "test_field": {
                    "type": "string",
                    "source": "env",
                    "default": "test",
                },
            },
        }
        schema_file.write_text(json.dumps(schema_data), encoding="utf-8")

        # Test with explicit service version
        response = get_configuration_schema_response(
            "test-service",
            schema_dir=str(schema_dir),
            service_version="0.5.0",
        )

        assert response["service_name"] == "test-service"
        assert response["service_version"] == "0.5.0"
        assert response["schema_version"] == "1.0.0"
        assert response["min_service_version"] == "0.1.0"
        assert "schema" in response
        assert response["schema"]["service_name"] == "test-service"

    def test_get_schema_response_from_env(self, tmp_path):
        """Test getting schema response with version from environment."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        schema_file = schema_dir / "test-service.json"
        schema_data = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "fields": {
                "test_field": {
                    "type": "string",
                    "source": "env",
                    "default": "test",
                },
            },
        }
        schema_file.write_text(json.dumps(schema_data), encoding="utf-8")

        os.environ["SERVICE_VERSION"] = "1.2.3"

        try:
            response = get_configuration_schema_response(
                "test-service",
                schema_dir=str(schema_dir),
            )

            assert response["service_version"] == "1.2.3"
        finally:
            if "SERVICE_VERSION" in os.environ:
                del os.environ["SERVICE_VERSION"]

    def test_get_schema_response_missing_file(self, tmp_path):
        """Test that missing schema file raises error."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="Schema file not found"):
            get_configuration_schema_response(
                "nonexistent-service",
                schema_dir=str(schema_dir),
            )

    def test_get_schema_response_includes_full_schema(self, tmp_path):
        """Test that response includes full schema data."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        schema_file = schema_dir / "test-service.json"
        schema_data = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "fields": {
                "field1": {
                    "type": "string",
                    "source": "env",
                    "description": "Test field 1",
                },
                "field2": {
                    "type": "int",
                    "source": "env",
                    "default": 42,
                },
            },
        }
        schema_file.write_text(json.dumps(schema_data), encoding="utf-8")

        response = get_configuration_schema_response(
            "test-service",
            schema_dir=str(schema_dir),
        )

        # Verify full schema is included
        assert "schema" in response
        assert "fields" in response["schema"]
        assert "field1" in response["schema"]["fields"]
        assert "field2" in response["schema"]["fields"]
        assert response["schema"]["fields"]["field1"]["type"] == "string"
        assert response["schema"]["fields"]["field2"]["default"] == 42
