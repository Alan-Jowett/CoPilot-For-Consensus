# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for RoleStore admin methods."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.role_store import RoleStore


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self):
        self.role_store_type = "mongodb"
        self.role_store_collection = "user_roles"
        self.role_store_database = "auth"
        self.role_store_host = None
        self.role_store_port = None
        self.role_store_username = None
        self.role_store_password = None
        self.role_store_schema_dir = None


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
        with patch("app.role_store.FileSchemaProvider"):
            with patch("app.role_store.ValidatingDocumentStore") as mock_val_store:
                mock_val_store.return_value = mock_store
                config = MockConfig()
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
        """Test assigning roles to non-existent user raises error."""
        mock_store.query_documents.return_value = []

        with pytest.raises(ValueError, match="User record not found"):
            role_store.assign_roles(
                user_id="github:999",
                roles=["contributor"],
                admin_user_id="github:admin",
            )


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
