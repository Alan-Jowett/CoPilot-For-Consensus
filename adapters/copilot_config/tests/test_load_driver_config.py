# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for load_driver_config module."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from copilot_config.load_driver_config import (
    _get_adapter_schema,
    _get_driver_schema,
    _get_service_schema,
    load_driver_config,
)
from copilot_config.models import DriverConfig


class TestGetServiceSchema:
    """Tests for _get_service_schema function."""

    def test_get_service_schema_success(self, tmp_path):
        """Test successfully loading a service schema."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        services_dir = schema_dir / "services"
        services_dir.mkdir(parents=True)

        # Create a test service schema
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "adapters": {
                "message_bus": {"$ref": "../adapters/message_bus.json"}
            }
        }
        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Test loading the schema
        schema, schema_path = _get_service_schema("test-service", str(schema_dir))

        assert schema == service_schema
        assert schema_path == str(service_file)

    def test_get_service_schema_not_found(self, tmp_path):
        """Test that missing service schema raises FileNotFoundError."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="Service schema not found"):
            _get_service_schema("nonexistent-service", str(schema_dir))


class TestGetAdapterSchema:
    """Tests for _get_adapter_schema function."""

    def test_get_adapter_schema_without_service(self, tmp_path):
        """Test loading adapter schema directly without service validation."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir(parents=True)

        # Create adapter schema
        adapter_schema = {
            "title": "Message Bus adapter",
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/rabbitmq.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Test loading adapter schema without service
        schema, schema_path = _get_adapter_schema(None, "message_bus", str(schema_dir))

        assert schema == adapter_schema
        assert schema_path == str(adapter_file)

    def test_get_adapter_schema_with_service_validation(self, tmp_path):
        """Test loading adapter schema with service validation."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        services_dir = schema_dir / "services"
        adapters_dir = schema_dir / "adapters"
        services_dir.mkdir(parents=True)
        adapters_dir.mkdir(parents=True)

        # Create service schema
        service_schema = {
            "service_name": "chunking",
            "adapters": {
                "message_bus": {"$ref": "../adapters/message_bus.json"}
            }
        }
        service_file = services_dir / "chunking.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "title": "Message Bus adapter",
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/rabbitmq.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Test loading adapter schema with service validation
        schema, schema_path = _get_adapter_schema("chunking", "message_bus", str(schema_dir))

        assert schema == adapter_schema
        assert schema_path == str(adapter_file)

    def test_get_adapter_schema_with_properties_structure(self, tmp_path):
        """Test loading adapter schema when service uses properties structure."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        services_dir = schema_dir / "services"
        adapters_dir = schema_dir / "adapters"
        services_dir.mkdir(parents=True)
        adapters_dir.mkdir(parents=True)

        # Create service schema with properties structure
        service_schema = {
            "service_name": "test-service",
            "properties": {
                "adapters": {
                    "properties": {
                        "logger": {"$ref": "../adapters/logger.json"}
                    }
                }
            }
        }
        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "title": "Logger adapter",
            "properties": {
                "drivers": {
                    "properties": {
                        "stdout": {"$ref": "./drivers/logger/stdout.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "logger.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Test loading adapter schema
        schema, schema_path = _get_adapter_schema("test-service", "logger", str(schema_dir))

        assert schema == adapter_schema
        assert schema_path == str(adapter_file)

    def test_get_adapter_schema_not_found_without_service(self, tmp_path):
        """Test that missing adapter schema raises FileNotFoundError when service is None."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="Adapter schema not found"):
            _get_adapter_schema(None, "nonexistent-adapter", str(schema_dir))

    def test_get_adapter_schema_not_declared_in_service(self, tmp_path):
        """Test that adapter not declared in service raises ValueError."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        services_dir = schema_dir / "services"
        services_dir.mkdir(parents=True)

        # Create service schema without the requested adapter
        service_schema = {
            "service_name": "test-service",
            "adapters": {
                "logger": {"$ref": "../adapters/logger.json"}
            }
        }
        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        with pytest.raises(ValueError, match="does not declare adapter"):
            _get_adapter_schema("test-service", "message_bus", str(schema_dir))

    def test_get_adapter_schema_no_ref(self, tmp_path):
        """Test that adapter without $ref raises ValueError."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        services_dir = schema_dir / "services"
        services_dir.mkdir(parents=True)

        # Create service schema with adapter but no $ref
        service_schema = {
            "service_name": "test-service",
            "adapters": {
                "message_bus": {"type": "object"}
            }
        }
        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        with pytest.raises(ValueError, match="has no schema reference"):
            _get_adapter_schema("test-service", "message_bus", str(schema_dir))

    def test_get_adapter_schema_ref_file_not_found(self, tmp_path):
        """Test that adapter with invalid $ref raises FileNotFoundError."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        services_dir = schema_dir / "services"
        services_dir.mkdir(parents=True)

        # Create service schema with adapter pointing to non-existent file
        service_schema = {
            "service_name": "test-service",
            "adapters": {
                "message_bus": {"$ref": "../adapters/missing.json"}
            }
        }
        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        with pytest.raises(FileNotFoundError, match="Adapter schema not found"):
            _get_adapter_schema("test-service", "message_bus", str(schema_dir))


class TestGetDriverSchema:
    """Tests for _get_driver_schema function."""

    def test_get_driver_schema_success(self, tmp_path):
        """Test successfully loading a driver schema."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        drivers_dir = adapters_dir / "drivers" / "message_bus"
        drivers_dir.mkdir(parents=True)

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/rabbitmq.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema
        driver_schema = {
            "title": "RabbitMQ driver",
            "properties": {
                "rabbitmq_host": {"type": "string", "default": "messagebus"},
                "rabbitmq_port": {"type": "int", "default": 5672}
            }
        }
        driver_file = drivers_dir / "rabbitmq.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Test loading driver schema
        schema, schema_path = _get_driver_schema(None, "message_bus", "rabbitmq", str(schema_dir))

        assert schema == driver_schema
        assert schema_path == str(driver_file)

    def test_get_driver_schema_not_supported_by_adapter(self, tmp_path):
        """Test that driver not supported by adapter raises ValueError."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir(parents=True)

        # Create adapter schema without the requested driver
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/rabbitmq.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        with pytest.raises(ValueError, match="does not support driver"):
            _get_driver_schema(None, "message_bus", "kafka", str(schema_dir))

    def test_get_driver_schema_no_ref(self, tmp_path):
        """Test that driver without $ref raises ValueError."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir(parents=True)

        # Create adapter schema with driver but no $ref
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"type": "object"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        with pytest.raises(ValueError, match="has no schema reference"):
            _get_driver_schema(None, "message_bus", "rabbitmq", str(schema_dir))

    def test_get_driver_schema_ref_file_not_found(self, tmp_path):
        """Test that driver with invalid $ref raises FileNotFoundError."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir(parents=True)

        # Create adapter schema with driver pointing to non-existent file
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/missing.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        with pytest.raises(FileNotFoundError, match="Driver schema not found"):
            _get_driver_schema(None, "message_bus", "rabbitmq", str(schema_dir))


class TestLoadDriverConfig:
    """Tests for load_driver_config function."""

    def test_load_driver_config_basic(self, tmp_path):
        """Test basic driver config loading with defaults."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        drivers_dir = adapters_dir / "drivers" / "message_bus"
        drivers_dir.mkdir(parents=True)

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/rabbitmq.json"}
                    }
                },
                "common": {
                    "properties": {
                        "timeout": {"type": "int", "default": 30}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema with defaults
        driver_schema = {
            "properties": {
                "rabbitmq_host": {"type": "string", "default": "messagebus"},
                "rabbitmq_port": {"type": "int", "default": 5672}
            }
        }
        driver_file = drivers_dir / "rabbitmq.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Load driver config
        config = load_driver_config(
            service=None,
            adapter="message_bus",
            driver="rabbitmq",
            fields=None,
            schema_dir=str(schema_dir)
        )

        assert isinstance(config, DriverConfig)
        assert config.driver_name == "rabbitmq"
        assert config.config["rabbitmq_host"] == "messagebus"
        assert config.config["rabbitmq_port"] == 5672
        assert config.config["timeout"] == 30
        assert "rabbitmq_host" in config.allowed_keys
        assert "rabbitmq_port" in config.allowed_keys
        assert "timeout" in config.allowed_keys

    def test_load_driver_config_with_fields(self, tmp_path):
        """Test loading driver config with custom field values."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        drivers_dir = adapters_dir / "drivers" / "message_bus"
        drivers_dir.mkdir(parents=True)

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/rabbitmq.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema
        driver_schema = {
            "properties": {
                "rabbitmq_host": {"type": "string", "default": "messagebus"},
                "rabbitmq_port": {"type": "int", "default": 5672},
                "rabbitmq_username": {"type": "string"}
            }
        }
        driver_file = drivers_dir / "rabbitmq.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Load driver config with custom fields
        config = load_driver_config(
            service=None,
            adapter="message_bus",
            driver="rabbitmq",
            fields={
                "rabbitmq_host": "custom-host",
                "rabbitmq_username": "admin"
            },
            schema_dir=str(schema_dir)
        )

        assert config.driver_name == "rabbitmq"
        assert config.config["rabbitmq_host"] == "custom-host"
        assert config.config["rabbitmq_port"] == 5672  # default
        assert config.config["rabbitmq_username"] == "admin"

    def test_load_driver_config_with_service_validation(self, tmp_path):
        """Test loading driver config with service validation."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        services_dir = schema_dir / "services"
        adapters_dir = schema_dir / "adapters"
        drivers_dir = adapters_dir / "drivers" / "message_bus"
        services_dir.mkdir(parents=True)
        drivers_dir.mkdir(parents=True)

        # Create service schema
        service_schema = {
            "service_name": "chunking",
            "adapters": {
                "message_bus": {"$ref": "../adapters/message_bus.json"}
            }
        }
        service_file = services_dir / "chunking.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/rabbitmq.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema
        driver_schema = {
            "properties": {
                "rabbitmq_host": {"type": "string", "default": "messagebus"}
            }
        }
        driver_file = drivers_dir / "rabbitmq.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Load driver config with service
        config = load_driver_config(
            service="chunking",
            adapter="message_bus",
            driver="rabbitmq",
            fields=None,
            schema_dir=str(schema_dir)
        )

        assert config.driver_name == "rabbitmq"
        assert config.config["rabbitmq_host"] == "messagebus"

    def test_load_driver_config_invalid_field(self, tmp_path):
        """Test that providing invalid field name raises AttributeError."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        drivers_dir = adapters_dir / "drivers" / "message_bus"
        drivers_dir.mkdir(parents=True)

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/rabbitmq.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema
        driver_schema = {
            "properties": {
                "rabbitmq_host": {"type": "string", "default": "messagebus"}
            }
        }
        driver_file = drivers_dir / "rabbitmq.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Try to load with invalid field
        with pytest.raises(AttributeError, match="not defined in"):
            load_driver_config(
                service=None,
                adapter="message_bus",
                driver="rabbitmq",
                fields={"invalid_field": "value"},
                schema_dir=str(schema_dir)
            )

    def test_load_driver_config_required_field_missing(self, tmp_path):
        """Test that missing required field raises ValueError."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        drivers_dir = adapters_dir / "drivers" / "message_bus"
        drivers_dir.mkdir(parents=True)

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/rabbitmq.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema with required field
        driver_schema = {
            "properties": {
                "api_key": {"type": "string", "required": True}
            }
        }
        driver_file = drivers_dir / "rabbitmq.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Try to load without required field
        with pytest.raises(ValueError, match="Missing required field"):
            load_driver_config(
                service=None,
                adapter="message_bus",
                driver="rabbitmq",
                fields=None,
                schema_dir=str(schema_dir)
            )

    def test_load_driver_config_with_common_properties(self, tmp_path):
        """Test that common properties from adapter schema are included."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        drivers_dir = adapters_dir / "drivers" / "message_bus"
        drivers_dir.mkdir(parents=True)

        # Create adapter schema with common properties
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "rabbitmq": {"$ref": "./drivers/message_bus/rabbitmq.json"}
                    }
                },
                "common": {
                    "properties": {
                        "timeout": {"type": "int", "default": 30},
                        "retry_count": {"type": "int", "default": 3}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema
        driver_schema = {
            "properties": {
                "rabbitmq_host": {"type": "string", "default": "messagebus"}
            }
        }
        driver_file = drivers_dir / "rabbitmq.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Load driver config
        config = load_driver_config(
            service=None,
            adapter="message_bus",
            driver="rabbitmq",
            fields={"timeout": 60},
            schema_dir=str(schema_dir)
        )

        assert config.driver_name == "rabbitmq"
        assert config.config["rabbitmq_host"] == "messagebus"
        assert config.config["timeout"] == 60
        assert config.config["retry_count"] == 3
        assert "timeout" in config.allowed_keys
        assert "retry_count" in config.allowed_keys

    def test_load_driver_config_empty_driver_properties(self, tmp_path):
        """Test loading driver config when driver schema has None for properties."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        adapters_dir = schema_dir / "adapters"
        drivers_dir = adapters_dir / "drivers" / "message_bus"
        drivers_dir.mkdir(parents=True)

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "drivers": {
                    "properties": {
                        "noop": {"$ref": "./drivers/message_bus/noop.json"}
                    }
                }
            }
        }
        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema with no properties
        driver_schema = {
            "title": "NoOp driver",
            "properties": None
        }
        driver_file = drivers_dir / "noop.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Load driver config
        config = load_driver_config(
            service=None,
            adapter="message_bus",
            driver="noop",
            fields=None,
            schema_dir=str(schema_dir)
        )

        assert config.driver_name == "noop"
        assert config.config == {}
        assert config.allowed_keys == set()
