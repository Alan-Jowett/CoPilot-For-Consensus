# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for first user auto-promotion security feature."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.role_store import RoleStore
from copilot_auth.models import User
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_Inmemory,
)
from copilot_config.generated.adapters.logger import (
    AdapterConfig_Logger,
    DriverConfig_Logger_Stdout,
)
from copilot_config.generated.adapters.metrics import (
    AdapterConfig_Metrics,
    DriverConfig_Metrics_Noop,
)
from copilot_config.generated.adapters.oidc_providers import (
    AdapterConfig_OidcProviders,
    CompositeConfig_OidcProviders,
)
from copilot_config.generated.adapters.secret_provider import (
    AdapterConfig_SecretProvider,
    DriverConfig_SecretProvider_Local,
)
from copilot_config.generated.services.auth import ServiceConfig_Auth, ServiceSettings_Auth


@pytest.fixture
def mock_store():
    """Create a mock document store."""
    store = MagicMock()
    store.query_documents = MagicMock(return_value=[])
    store.insert_document = MagicMock()
    store.update_document = MagicMock()
    return store


@pytest.fixture
def role_store(mock_store):
    """Create a RoleStore instance with mocked dependencies."""
    with patch("app.role_store.create_document_store", return_value=mock_store):
        with patch("app.role_store.create_schema_provider"):
            config = ServiceConfig_Auth(
                service_settings=ServiceSettings_Auth(issuer="http://localhost:8090"),
                document_store=AdapterConfig_DocumentStore(
                    doc_store_type="inmemory",
                    driver=DriverConfig_DocumentStore_Inmemory(),
                ),
                logger=AdapterConfig_Logger(
                    logger_type="stdout",
                    driver=DriverConfig_Logger_Stdout(),
                ),
                metrics=AdapterConfig_Metrics(
                    metrics_type="noop",
                    driver=DriverConfig_Metrics_Noop(),
                ),
                oidc_providers=AdapterConfig_OidcProviders(
                    oidc_providers=CompositeConfig_OidcProviders(),
                ),
                secret_provider=AdapterConfig_SecretProvider(
                    secret_provider_type="local",
                    driver=DriverConfig_SecretProvider_Local(),
                ),
            )
            return RoleStore(config)


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    return User(
        id="github:12345",
        email="test@example.com",
        name="Test User",
    )


class TestFirstUserAutoPromotion:
    """Test first user auto-promotion configuration."""

    def test_auto_promotion_disabled_by_default(self, role_store, mock_store, mock_user):
        """Test that auto-promotion is disabled when first_user_auto_promotion_enabled=False (default)."""
        # Mock: No existing users (empty database)
        mock_store.query_documents.return_value = []

        # Call with default parameter (disabled auto-promotion)
        roles, status = role_store.get_roles_for_user(
            user=mock_user,
            auto_approve_enabled=False,
            auto_approve_roles=[],
            first_user_auto_promotion_enabled=False,  # Default secure setting
        )

        # Should NOT auto-promote to admin
        assert roles == []
        assert status == "pending"

        # Verify insert was called with pending status
        mock_store.insert_document.assert_called_once()
        insert_args = mock_store.insert_document.call_args[0]
        doc = insert_args[1]
        assert doc["roles"] == []
        assert doc["status"] == "pending"

    def test_auto_promotion_enabled_in_dev_mode(self, role_store, mock_store, mock_user):
        """Test that auto-promotion works when explicitly enabled (development mode)."""
        # Mock: No existing users (empty database)
        mock_store.query_documents.return_value = []

        # Call with auto-promotion explicitly enabled (development mode)
        roles, status = role_store.get_roles_for_user(
            user=mock_user,
            auto_approve_enabled=False,
            auto_approve_roles=[],
            first_user_auto_promotion_enabled=True,  # Enable for dev/testing
        )

        # Should auto-promote to admin + reader
        assert roles == ["admin", "reader"]
        assert status == "approved"

        # Verify insert was called with admin + reader roles
        mock_store.insert_document.assert_called_once()
        insert_args = mock_store.insert_document.call_args[0]
        doc = insert_args[1]
        assert doc["roles"] == ["admin", "reader"]
        assert doc["status"] == "approved"

    def test_auto_promotion_only_when_no_admins_exist(self, role_store, mock_store, mock_user):
        """Test that auto-promotion only happens when no admins exist."""
        # Mock: Existing admin user
        existing_admin = {
            "user_id": "github:admin",
            "roles": ["admin"],
            "status": "approved",
        }

        # First call returns no user record, second call returns existing admin
        def mock_query(collection, query, limit=None):
            if query.get("user_id") == mock_user.id:
                return []  # New user has no record
            elif "roles" in query and query["roles"] == "admin":
                return [existing_admin]  # Admin already exists
            return []

        mock_store.query_documents.side_effect = mock_query

        # Call with auto-promotion enabled
        roles, status = role_store.get_roles_for_user(
            user=mock_user,
            auto_approve_enabled=False,
            auto_approve_roles=[],
            first_user_auto_promotion_enabled=True,  # Enabled
        )

        # Should NOT auto-promote since admin already exists
        assert roles == []
        assert status == "pending"

    def test_existing_user_not_affected(self, role_store, mock_store, mock_user):
        """Test that existing users are not affected by auto-promotion setting."""
        # Mock: Existing user with contributor role
        existing_user = {
            "user_id": mock_user.id,
            "roles": ["contributor"],
            "status": "approved",
        }
        mock_store.query_documents.return_value = [existing_user]

        # Call with auto-promotion disabled
        roles, status = role_store.get_roles_for_user(
            user=mock_user,
            auto_approve_enabled=False,
            auto_approve_roles=[],
            first_user_auto_promotion_enabled=False,
        )

        # Should return existing roles (not affected by auto-promotion setting)
        assert roles == ["contributor"]
        assert status == "approved"

        # Should not insert a new record
        mock_store.insert_document.assert_not_called()

    def test_auto_approve_works_when_auto_promotion_disabled(self, role_store, mock_store, mock_user):
        """Test that auto-approve works when first-user auto-promotion is disabled."""
        # Mock: No existing users
        mock_store.query_documents.return_value = []

        # Call with auto-promotion disabled AND auto-approve enabled
        roles, status = role_store.get_roles_for_user(
            user=mock_user,
            auto_approve_enabled=True,
            auto_approve_roles=["contributor", "reviewer"],
            first_user_auto_promotion_enabled=False,  # Disabled
        )

        # Should use auto-approve roles, not admin
        assert set(roles) == {"contributor", "reviewer"}
        assert status == "approved"

    def test_auto_promotion_fallback_to_auto_approve(self, role_store, mock_store, mock_user):
        """Test that when auto-promotion is enabled but admin exists, auto-approve is used."""
        # Mock: Existing admin user
        existing_admin = {
            "user_id": "github:admin",
            "roles": ["admin"],
            "status": "approved",
        }

        # Setup query to return no user record but existing admin
        def mock_query(collection, query, limit=None):
            if query.get("user_id") == mock_user.id:
                return []
            elif "roles" in query and query["roles"] == "admin":
                return [existing_admin]
            return []

        mock_store.query_documents.side_effect = mock_query

        # Call with auto-promotion enabled AND auto-approve enabled
        roles, status = role_store.get_roles_for_user(
            user=mock_user,
            auto_approve_enabled=True,
            auto_approve_roles=["reader"],
            first_user_auto_promotion_enabled=True,  # Enabled but admin exists
        )

        # Should use auto-approve since admin already exists
        assert roles == ["reader"]
        assert status == "approved"

    def test_denied_user_not_affected(self, role_store, mock_store, mock_user):
        """Test that denied users remain denied regardless of auto-promotion setting."""
        # Mock: User with denied status
        denied_user = {
            "user_id": mock_user.id,
            "roles": [],
            "status": "denied",
        }
        mock_store.query_documents.return_value = [denied_user]

        # Call with auto-promotion enabled
        roles, status = role_store.get_roles_for_user(
            user=mock_user,
            auto_approve_enabled=False,
            auto_approve_roles=[],
            first_user_auto_promotion_enabled=True,  # Enabled
        )

        # Should remain denied (not auto-promoted)
        assert roles == []
        assert status == "denied"
