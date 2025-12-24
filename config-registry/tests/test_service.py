# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Config Registry service."""

import pytest
from app.models import ConfigUpdate
from app.service import ConfigRegistryService
from copilot_storage import create_document_store


@pytest.fixture
def in_memory_store():
    """Create in-memory document store."""
    store = create_document_store(store_type="inmemory")
    store.connect()
    return store


@pytest.fixture
def registry_service(in_memory_store):
    """Create registry service with in-memory store."""
    return ConfigRegistryService(doc_store=in_memory_store)


class TestConfigRegistry:
    """Test suite for Config Registry service."""

    def test_create_config(self, registry_service):
        """Test creating a new configuration."""
        config_data = {"db_host": "localhost", "db_port": 5432}

        doc = registry_service.create_config(
            service_name="test-service",
            config_data=config_data,
            environment="dev",
            created_by="test-user",
            comment="Initial config",
        )

        assert doc.service_name == "test-service"
        assert doc.environment == "dev"
        assert doc.version == 1
        assert doc.config_data == config_data
        assert doc.created_by == "test-user"

    def test_create_duplicate_config_fails(self, registry_service):
        """Test that creating a duplicate config fails."""
        config_data = {"db_host": "localhost"}

        registry_service.create_config(
            service_name="test-service", config_data=config_data, environment="dev"
        )

        with pytest.raises(ValueError, match="already exists"):
            registry_service.create_config(
                service_name="test-service", config_data=config_data, environment="dev"
            )

    def test_get_config(self, registry_service):
        """Test retrieving a configuration."""
        config_data = {"db_host": "localhost", "db_port": 5432}

        registry_service.create_config(
            service_name="test-service", config_data=config_data, environment="dev"
        )

        retrieved = registry_service.get_config("test-service", "dev")
        assert retrieved == config_data

    def test_get_nonexistent_config_returns_none(self, registry_service):
        """Test that getting a nonexistent config returns None."""
        result = registry_service.get_config("nonexistent", "dev")
        assert result is None

    def test_update_config(self, registry_service):
        """Test updating a configuration."""
        config_data_v1 = {"db_host": "localhost", "db_port": 5432}
        config_data_v2 = {"db_host": "production-db", "db_port": 5432}

        registry_service.create_config(
            service_name="test-service", config_data=config_data_v1, environment="dev"
        )

        doc = registry_service.update_config(
            service_name="test-service",
            config_data=config_data_v2,
            environment="dev",
            comment="Updated db host",
        )

        assert doc.version == 2
        assert doc.config_data == config_data_v2

        # Verify latest is retrieved
        latest = registry_service.get_config("test-service", "dev")
        assert latest == config_data_v2

    def test_update_nonexistent_config_fails(self, registry_service):
        """Test that updating a nonexistent config fails."""
        with pytest.raises(ValueError, match="does not exist"):
            registry_service.update_config(
                service_name="nonexistent", config_data={"key": "value"}, environment="dev"
            )

    def test_get_config_specific_version(self, registry_service):
        """Test retrieving a specific configuration version."""
        config_data_v1 = {"db_host": "localhost"}
        config_data_v2 = {"db_host": "production-db"}

        registry_service.create_config(
            service_name="test-service", config_data=config_data_v1, environment="dev"
        )
        registry_service.update_config(
            service_name="test-service", config_data=config_data_v2, environment="dev"
        )

        # Get v1
        v1 = registry_service.get_config("test-service", "dev", version=1)
        assert v1 == config_data_v1

        # Get v2
        v2 = registry_service.get_config("test-service", "dev", version=2)
        assert v2 == config_data_v2

    def test_list_configs(self, registry_service):
        """Test listing configurations."""
        registry_service.create_config(
            service_name="service-a", config_data={"key": "value"}, environment="dev"
        )
        registry_service.create_config(
            service_name="service-b", config_data={"key": "value"}, environment="dev"
        )
        registry_service.create_config(
            service_name="service-c", config_data={"key": "value"}, environment="prod"
        )

        # List all
        all_configs = registry_service.list_configs()
        assert len(all_configs) == 3

        # Filter by service
        service_a_configs = registry_service.list_configs(service_name="service-a")
        assert len(service_a_configs) == 1
        assert service_a_configs[0]["service_name"] == "service-a"

        # Filter by environment
        dev_configs = registry_service.list_configs(environment="dev")
        assert len(dev_configs) == 2

    def test_get_config_history(self, registry_service):
        """Test retrieving configuration history."""
        registry_service.create_config(
            service_name="test-service", config_data={"version": 1}, environment="dev"
        )
        registry_service.update_config(
            service_name="test-service", config_data={"version": 2}, environment="dev"
        )
        registry_service.update_config(
            service_name="test-service", config_data={"version": 3}, environment="dev"
        )

        history = registry_service.get_config_history("test-service", "dev", limit=10)
        assert len(history) == 3
        assert history[0]["version"] == 3  # Newest first
        assert history[1]["version"] == 2
        assert history[2]["version"] == 1

    def test_diff_configs(self, registry_service):
        """Test configuration diffing."""
        config_v1 = {"db_host": "localhost", "db_port": 5432, "old_field": "value"}
        config_v2 = {"db_host": "production-db", "db_port": 5432, "new_field": "value"}

        registry_service.create_config(
            service_name="test-service", config_data=config_v1, environment="dev"
        )
        registry_service.update_config(
            service_name="test-service", config_data=config_v2, environment="dev"
        )

        diff = registry_service.diff_configs("test-service", "dev", old_version=1, new_version=2)

        assert diff.old_version == 1
        assert diff.new_version == 2
        assert "new_field" in diff.added
        assert "old_field" in diff.removed
        assert "db_host" in diff.changed
        assert diff.changed["db_host"]["old"] == "localhost"
        assert diff.changed["db_host"]["new"] == "production-db"

    def test_delete_config(self, registry_service):
        """Test deleting a configuration."""
        registry_service.create_config(
            service_name="test-service", config_data={"key": "value"}, environment="dev"
        )

        count = registry_service.delete_config("test-service", "dev")
        assert count == 1

        # Verify deleted
        result = registry_service.get_config("test-service", "dev")
        assert result is None

    def test_stats_tracking(self, registry_service):
        """Test that service tracks statistics."""
        stats = registry_service.get_stats()
        initial_created = stats["configs_created"]
        initial_updated = stats["configs_updated"]
        initial_retrieved = stats["configs_retrieved"]

        # Create config
        registry_service.create_config(
            service_name="test-service", config_data={"key": "value"}, environment="dev"
        )

        # Update config
        registry_service.update_config(
            service_name="test-service", config_data={"key": "value2"}, environment="dev"
        )

        # Get config
        registry_service.get_config("test-service", "dev")

        stats = registry_service.get_stats()
        assert stats["configs_created"] == initial_created + 1
        assert stats["configs_updated"] == initial_updated + 1
        assert stats["configs_retrieved"] == initial_retrieved + 1

    def test_environment_isolation(self, registry_service):
        """Test that environments are isolated."""
        dev_config = {"env": "dev", "debug": True}
        prod_config = {"env": "prod", "debug": False}

        registry_service.create_config(
            service_name="test-service", config_data=dev_config, environment="dev"
        )
        registry_service.create_config(
            service_name="test-service", config_data=prod_config, environment="prod"
        )

        # Verify isolation
        dev_result = registry_service.get_config("test-service", "dev")
        prod_result = registry_service.get_config("test-service", "prod")

        assert dev_result == dev_config
        assert prod_result == prod_config
        assert dev_result != prod_result
