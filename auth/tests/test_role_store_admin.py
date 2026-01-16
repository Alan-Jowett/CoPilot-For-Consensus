# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for RoleStore admin methods."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.role_store import RoleStore
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


class TestListPendingRoleAssignments:
    """Test list_pending_role_assignments method."""

    def test_list_pending_no_filters(self, role_store, mock_store):
        """Test listing all pending assignments without filters."""
        # Mock pending assignments
        pending_docs = [
            {
                "user_id": "github:123",
                "status": "pending",
                "roles": [],
                "requested_at": "2025-01-01T00:00:00Z",
            },
            {
                "user_id": "github:456",
                "status": "pending",
                "roles": [],
                "requested_at": "2025-01-02T00:00:00Z",
            },
        ]
        mock_store.query_documents.return_value = pending_docs

        assignments, total = role_store.list_pending_role_assignments()

        assert len(assignments) == 2
        assert total == 2
        mock_store.query_documents.assert_called_once()
        call_args = mock_store.query_documents.call_args
        assert call_args[0][1] == {"status": "pending"}

    def test_list_pending_with_user_filter(self, role_store, mock_store):
        """Test filtering by user ID."""
        pending_docs = [
            {
                "user_id": "github:123",
                "status": "pending",
                "roles": [],
                "requested_at": "2025-01-01T00:00:00Z",
            },
        ]
        mock_store.query_documents.return_value = pending_docs

        assignments, total = role_store.list_pending_role_assignments(user_id="github:123")

        assert len(assignments) == 1
        assert total == 1
        assert assignments[0]["user_id"] == "github:123"
        call_args = mock_store.query_documents.call_args
        assert call_args[0][1] == {"status": "pending", "user_id": "github:123"}

    def test_list_pending_with_role_filter(self, role_store, mock_store):
        """Test filtering by role."""
        pending_docs = [
            {
                "user_id": "github:123",
                "status": "pending",
                "roles": ["contributor"],
                "requested_at": "2025-01-01T00:00:00Z",
            },
        ]
        mock_store.query_documents.return_value = pending_docs

        assignments, total = role_store.list_pending_role_assignments(role="contributor")

        assert len(assignments) == 1
        assert total == 1
        call_args = mock_store.query_documents.call_args
        assert call_args[0][1] == {"status": "pending", "roles": "contributor"}

    def test_list_pending_pagination(self, role_store, mock_store):
        """Test pagination with skip and limit."""
        pending_docs = [
            {"user_id": f"github:{i}", "status": "pending", "requested_at": f"2025-01-{i:02d}T00:00:00Z"}
            for i in range(1, 11)
        ]
        mock_store.query_documents.return_value = pending_docs

        # Get second page (skip 5, limit 5)
        # Since default sort is descending on requested_at, we expect 10,9,8,7,6 then 5,4,3,2,1
        assignments, total = role_store.list_pending_role_assignments(skip=5, limit=5)

        assert len(assignments) == 5
        assert total == 10
        # After sorting descending and skipping 5, first item should be github:5
        assert assignments[0]["user_id"] == "github:5"

    def test_list_pending_sorting(self, role_store, mock_store):
        """Test sorting by field and order."""
        pending_docs = [
            {"user_id": "github:1", "status": "pending", "requested_at": "2025-01-03T00:00:00Z"},
            {"user_id": "github:2", "status": "pending", "requested_at": "2025-01-01T00:00:00Z"},
            {"user_id": "github:3", "status": "pending", "requested_at": "2025-01-02T00:00:00Z"},
        ]
        mock_store.query_documents.return_value = pending_docs

        # Sort descending (newest first)
        assignments, total = role_store.list_pending_role_assignments(sort_by="requested_at", sort_order=-1)

        assert assignments[0]["user_id"] == "github:1"
        assert assignments[1]["user_id"] == "github:3"
        assert assignments[2]["user_id"] == "github:2"


class TestGetUserRoles:
    """Test get_user_roles method."""

    def test_get_existing_user(self, role_store, mock_store):
        """Test getting roles for an existing user."""
        user_record = {
            "user_id": "github:123",
            "roles": ["contributor"],
            "status": "approved",
        }
        mock_store.query_documents.return_value = [user_record]

        result = role_store.get_user_roles("github:123")

        assert result == user_record
        mock_store.query_documents.assert_called_once()

    def test_get_nonexistent_user(self, role_store, mock_store):
        """Test getting roles for a non-existent user."""
        mock_store.query_documents.return_value = []

        result = role_store.get_user_roles("github:999")

        assert result is None


class TestAssignRoles:
    """Test assign_roles method."""

    def test_assign_roles_success(self, role_store, mock_store):
        """Test successfully assigning roles to a user."""
        existing_record = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "user_id": "github:123",
            "roles": [],
            "status": "pending",
            "requested_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        mock_store.query_documents.return_value = [existing_record]

        result = role_store.assign_roles(
            user_id="github:123",
            roles=["contributor", "reviewer"],
            admin_user_id="github:admin",
            admin_email="admin@example.com",
        )

        assert result["roles"] == ["contributor", "reviewer"]
        assert result["status"] == "approved"
        assert "approved_by" in result
        assert result["approved_by"] == "github:admin"
        assert "approved_at" in result
        mock_store.update_document.assert_called_once()

    def test_assign_roles_user_not_found(self, role_store, mock_store):
        """Test assigning roles to non-existent user creates new record."""
        mock_store.query_documents.return_value = []

        result = role_store.assign_roles(
            user_id="github:999",
            roles=["contributor"],
            admin_user_id="github:admin",
        )

        # Should create a new record with the roles
        assert result["user_id"] == "github:999"
        assert result["roles"] == ["contributor"]
        assert result["status"] == "approved"
        assert result["approved_by"] == "github:admin"
        # Should insert (not update) since no existing record
        mock_store.insert_document.assert_called_once()

    def test_assign_roles_invalid_role(self, role_store, mock_store):
        """Test assigning invalid roles raises error."""
        existing_record = {
            "user_id": "github:123",
            "roles": [],
            "status": "pending",
        }
        mock_store.query_documents.return_value = [existing_record]

        with pytest.raises(ValueError, match="Invalid roles: super-admin"):
            role_store.assign_roles(
                user_id="github:123",
                roles=["contributor", "super-admin"],
                admin_user_id="github:admin",
            )

    def test_assign_roles_excludes_id_from_update(self, role_store, mock_store):
        """Test that _id field is excluded from update document (MongoDB immutable field)."""
        # Include _id in the record (simulating MongoDB document)
        existing_record = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "user_id": "github:123",
            "roles": [],
            "status": "pending",
        }
        mock_store.query_documents.return_value = [existing_record]

        role_store.assign_roles(
            user_id="github:123",
            roles=["contributor"],
            admin_user_id="github:admin",
        )

        # Verify update_document was called
        mock_store.update_document.assert_called_once()

        # Get the update document that was passed (third argument)
        call_args = mock_store.update_document.call_args
        update_doc = call_args[0][2]

        # Verify _id is NOT in the update document
        assert "_id" not in update_doc, "update document should not contain _id field"
        # Verify other fields are present
        assert update_doc["user_id"] == "github:123"
        assert update_doc["roles"] == ["contributor"]
        assert update_doc["status"] == "approved"

    def test_assign_roles_merges_with_existing(self, role_store, mock_store):
        """Test that assigning roles merges with existing roles (additive)."""
        existing_record = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "user_id": "github:123",
            "roles": ["reader"],
            "status": "approved",
            "requested_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        mock_store.query_documents.return_value = [existing_record]

        result = role_store.assign_roles(
            user_id="github:123",
            roles=["contributor", "reviewer"],
            admin_user_id="github:admin",
        )

        # Should merge: reader + contributor + reviewer
        assert set(result["roles"]) == {"reader", "contributor", "reviewer"}
        assert result["status"] == "approved"
        mock_store.update_document.assert_called_once()

    def test_assign_roles_deduplicates(self, role_store, mock_store):
        """Test that assigning duplicate roles doesn't create duplicates."""
        existing_record = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "user_id": "github:123",
            "roles": ["contributor", "reader"],
            "status": "approved",
        }
        mock_store.query_documents.return_value = [existing_record]

        result = role_store.assign_roles(
            user_id="github:123",
            roles=["contributor", "reviewer"],  # contributor is duplicate
            admin_user_id="github:admin",
        )

        # Should have: contributor, reader, reviewer (no duplicate contributor)
        assert len(result["roles"]) == 3
        assert set(result["roles"]) == {"contributor", "reader", "reviewer"}
        mock_store.update_document.assert_called_once()


class TestRevokeRoles:
    """Test revoke_roles method."""

    def test_revoke_roles_success(self, role_store, mock_store):
        """Test successfully revoking roles from a user."""
        existing_record = {
            "user_id": "github:123",
            "roles": ["contributor", "reviewer", "admin"],
            "status": "approved",
        }
        mock_store.query_documents.return_value = [existing_record]

        result = role_store.revoke_roles(
            user_id="github:123",
            roles=["admin"],
            admin_user_id="github:superadmin",
            admin_email="superadmin@example.com",
        )

        assert result["roles"] == ["contributor", "reviewer"]
        assert "last_modified_by" in result
        assert result["last_modified_by"] == "github:superadmin"
        mock_store.update_document.assert_called_once()

    def test_revoke_multiple_roles(self, role_store, mock_store):
        """Test revoking multiple roles at once."""
        existing_record = {
            "user_id": "github:123",
            "roles": ["contributor", "reviewer", "admin"],
            "status": "approved",
        }
        mock_store.query_documents.return_value = [existing_record]

        result = role_store.revoke_roles(
            user_id="github:123",
            roles=["reviewer", "admin"],
            admin_user_id="github:superadmin",
        )

        assert result["roles"] == ["contributor"]

    def test_revoke_roles_user_not_found(self, role_store, mock_store):
        """Test revoking roles from non-existent user raises error."""
        mock_store.query_documents.return_value = []

        with pytest.raises(ValueError, match="User record not found"):
            role_store.revoke_roles(
                user_id="github:999",
                roles=["admin"],
                admin_user_id="github:admin",
            )

    def test_revoke_nonexistent_role(self, role_store, mock_store):
        """Test revoking a role the user doesn't have (should succeed silently)."""
        existing_record = {
            "user_id": "github:123",
            "roles": ["contributor"],
            "status": "approved",
        }
        mock_store.query_documents.return_value = [existing_record]

        result = role_store.revoke_roles(
            user_id="github:123",
            roles=["admin"],  # User doesn't have this role
            admin_user_id="github:superadmin",
        )

        # Roles should remain unchanged
        assert result["roles"] == ["contributor"]

    def test_revoke_invalid_role(self, role_store, mock_store):
        """Test revoking invalid roles raises error."""
        existing_record = {
            "user_id": "github:123",
            "roles": ["contributor"],
            "status": "approved",
        }
        mock_store.query_documents.return_value = [existing_record]

        with pytest.raises(ValueError, match="Invalid roles: fake-role"):
            role_store.revoke_roles(
                user_id="github:123",
                roles=["fake-role"],
                admin_user_id="github:admin",
            )

    def test_revoke_roles_excludes_id_from_update(self, role_store, mock_store):
        """Test that _id field is excluded from update document (MongoDB immutable field)."""
        # Include _id in the record (simulating MongoDB document)
        existing_record = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "user_id": "github:123",
            "roles": ["contributor", "admin"],
            "status": "approved",
        }
        mock_store.query_documents.return_value = [existing_record]

        role_store.revoke_roles(
            user_id="github:123",
            roles=["admin"],
            admin_user_id="github:superadmin",
        )

        # Verify update_document was called
        mock_store.update_document.assert_called_once()

        # Get the update document that was passed (third argument)
        call_args = mock_store.update_document.call_args
        update_doc = call_args[0][2]

        # Verify _id is NOT in the update document
        assert "_id" not in update_doc, "update document should not contain _id field"
        # Verify other fields are present
        assert update_doc["user_id"] == "github:123"
        assert update_doc["roles"] == ["contributor"]
        assert "last_modified_by" in update_doc


class TestSearchUsers:
    """Test search_users method."""

    def test_search_by_user_id_exact_match(self, role_store, mock_store):
        """Test searching by user_id with exact match."""
        user_record = {
            "user_id": "github:123",
            "email": "user@example.com",
            "name": "Test User",
            "roles": ["contributor"],
            "status": "approved",
        }
        mock_store.query_documents.return_value = [user_record]

        results = role_store.search_users(search_term="github:123", search_by="user_id")

        assert len(results) == 1
        assert results[0]["user_id"] == "github:123"
        mock_store.query_documents.assert_called_once_with("user_roles", {"user_id": "github:123"})

    def test_search_by_email_partial_match(self, role_store, mock_store):
        """Test searching by email with partial, case-insensitive match."""
        all_users = [
            {
                "user_id": "github:123",
                "email": "alice@example.com",
                "name": "Alice",
                "roles": ["admin"],
                "status": "approved",
            },
            {
                "user_id": "github:456",
                "email": "bob@example.com",
                "name": "Bob",
                "roles": ["contributor"],
                "status": "approved",
            },
            {
                "user_id": "github:789",
                "email": "charlie@other.com",
                "name": "Charlie",
                "roles": ["reader"],
                "status": "approved",
            },
        ]
        mock_store.query_documents.return_value = all_users

        results = role_store.search_users(search_term="example", search_by="email")

        assert len(results) == 2
        assert results[0]["email"] == "alice@example.com"
        assert results[1]["email"] == "bob@example.com"
        mock_store.query_documents.assert_called_once_with("user_roles", {})

    def test_search_by_name_case_insensitive(self, role_store, mock_store):
        """Test searching by name with case-insensitive partial match."""
        all_users = [
            {
                "user_id": "github:123",
                "email": "alice@example.com",
                "name": "Alice Smith",
                "roles": ["admin"],
                "status": "approved",
            },
            {
                "user_id": "github:456",
                "email": "bob@example.com",
                "name": "Bob Jones",
                "roles": ["contributor"],
                "status": "approved",
            },
        ]
        mock_store.query_documents.return_value = all_users

        results = role_store.search_users(search_term="alice", search_by="name")

        assert len(results) == 1
        assert results[0]["name"] == "Alice Smith"

    def test_search_invalid_field(self, role_store, mock_store):
        """Test searching by invalid field raises error."""
        with pytest.raises(ValueError, match="Invalid search_by field"):
            role_store.search_users(search_term="test", search_by="invalid_field")

    def test_search_no_results(self, role_store, mock_store):
        """Test searching returns empty list when no matches."""
        mock_store.query_documents.return_value = []

        results = role_store.search_users(search_term="nonexistent", search_by="email")

        assert len(results) == 0

    def test_search_handles_missing_field(self, role_store, mock_store):
        """Test searching handles users with missing search field gracefully."""
        all_users = [
            {
                "user_id": "github:123",
                "email": "alice@example.com",
                "name": "Alice",
                "roles": ["admin"],
                "status": "approved",
            },
            {
                "user_id": "github:456",
                # email field missing
                "name": "Bob",
                "roles": ["contributor"],
                "status": "approved",
            },
        ]
        mock_store.query_documents.return_value = all_users

        results = role_store.search_users(search_term="alice", search_by="email")

        # Should only find Alice, not crash on Bob's missing email
        assert len(results) == 1
        assert results[0]["user_id"] == "github:123"
