# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for admin endpoints."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_auth_service():
    """Create a mock auth service."""
    service = MagicMock()
    service.config.audiences = "copilot-for-consensus"

    # Mock role store
    role_store = MagicMock()
    service.role_store = role_store

    return service


@pytest.fixture
def client(mock_auth_service):
    """Create test client with mocked auth service."""
    # Patch before importing main
    with patch("sys.path", [str(Path(__file__).parent.parent)] + sys.path):
        # Import main module
        import main

        # Set the mock auth service
        main.auth_service = mock_auth_service

        return TestClient(main.app)


@pytest.fixture
def admin_token():
    """Generate a mock admin token."""
    return "mock-admin-token"


@pytest.fixture
def non_admin_token():
    """Generate a mock non-admin token."""
    return "mock-user-token"


class TestListPendingAssignments:
    """Test GET /admin/role-assignments/pending endpoint."""

    def test_list_pending_success(self, client, mock_auth_service, admin_token):
        """Test successfully listing pending assignments as admin."""
        # Mock token validation
        mock_auth_service.validate_token.return_value = {
            "sub": "github:admin",
            "email": "admin@example.com",
            "roles": ["admin"],
        }

        # Mock role store response
        pending_assignments = [
            {
                "user_id": "github:123",
                "email": "user1@example.com",
                "roles": [],
                "status": "pending",
                "requested_at": "2025-01-01T00:00:00Z",
            },
            {
                "user_id": "github:456",
                "email": "user2@example.com",
                "roles": [],
                "status": "pending",
                "requested_at": "2025-01-02T00:00:00Z",
            },
        ]
        mock_auth_service.role_store.list_pending_role_assignments.return_value = (pending_assignments, 2)

        response = client.get("/admin/role-assignments/pending", headers={"Authorization": f"Bearer {admin_token}"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["assignments"]) == 2
        assert data["total"] == 2
        assert data["limit"] == 50
        assert data["skip"] == 0

    def test_list_pending_with_filters(self, client, mock_auth_service, admin_token):
        """Test listing with user_id and role filters."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:admin",
            "email": "admin@example.com",
            "roles": ["admin"],
        }

        mock_auth_service.role_store.list_pending_role_assignments.return_value = ([], 0)

        response = client.get(
            "/admin/role-assignments/pending?user_id=github:123&role=contributor&limit=10&skip=5",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        # Verify the filters were passed to role_store
        mock_auth_service.role_store.list_pending_role_assignments.assert_called_once()
        call_kwargs = mock_auth_service.role_store.list_pending_role_assignments.call_args[1]
        assert call_kwargs["user_id"] == "github:123"
        assert call_kwargs["role"] == "contributor"
        assert call_kwargs["limit"] == 10
        assert call_kwargs["skip"] == 5

    def test_list_pending_no_admin_role(self, client, mock_auth_service, non_admin_token):
        """Test that non-admin users are rejected."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:user",
            "email": "user@example.com",
            "roles": ["contributor"],  # Not admin
        }

        response = client.get("/admin/role-assignments/pending", headers={"Authorization": f"Bearer {non_admin_token}"})

        assert response.status_code == 403
        assert "Admin role required" in response.json()["detail"]

    def test_list_pending_missing_token(self, client):
        """Test that missing token is rejected."""
        response = client.get("/admin/role-assignments/pending")

        assert response.status_code == 401
        assert "Missing or invalid Authorization header" in response.json()["detail"]


class TestGetUserRoles:
    """Test GET /admin/users/{user_id}/roles endpoint."""

    def test_get_user_roles_success(self, client, mock_auth_service, admin_token):
        """Test successfully getting user roles as admin."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:admin",
            "email": "admin@example.com",
            "roles": ["admin"],
        }

        user_record = {
            "user_id": "github:123",
            "email": "user@example.com",
            "roles": ["contributor"],
            "status": "approved",
        }
        mock_auth_service.role_store.get_user_roles.return_value = user_record

        response = client.get("/admin/users/github:123/roles", headers={"Authorization": f"Bearer {admin_token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "github:123"
        assert data["roles"] == ["contributor"]

    def test_get_user_roles_not_found(self, client, mock_auth_service, admin_token):
        """Test getting roles for non-existent user."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:admin",
            "email": "admin@example.com",
            "roles": ["admin"],
        }

        mock_auth_service.role_store.get_user_roles.return_value = None

        response = client.get("/admin/users/github:999/roles", headers={"Authorization": f"Bearer {admin_token}"})

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_get_user_roles_no_admin(self, client, mock_auth_service, non_admin_token):
        """Test that non-admin users cannot view roles."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:user",
            "email": "user@example.com",
            "roles": ["contributor"],
        }

        response = client.get("/admin/users/github:123/roles", headers={"Authorization": f"Bearer {non_admin_token}"})

        assert response.status_code == 403


class TestAssignUserRoles:
    """Test POST /admin/users/{user_id}/roles endpoint."""

    def test_assign_roles_success(self, client, mock_auth_service, admin_token):
        """Test successfully assigning roles as admin."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:admin",
            "email": "admin@example.com",
            "roles": ["admin"],
        }

        updated_record = {
            "user_id": "github:123",
            "roles": ["contributor", "reviewer"],
            "status": "approved",
            "approved_by": "github:admin",
        }
        mock_auth_service.role_store.assign_roles.return_value = updated_record

        response = client.post(
            "/admin/users/github:123/roles",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"roles": ["contributor", "reviewer"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["roles"] == ["contributor", "reviewer"]
        assert data["status"] == "approved"

        # Verify role store was called correctly
        mock_auth_service.role_store.assign_roles.assert_called_once()
        call_kwargs = mock_auth_service.role_store.assign_roles.call_args[1]
        assert call_kwargs["user_id"] == "github:123"
        assert call_kwargs["roles"] == ["contributor", "reviewer"]
        assert call_kwargs["admin_user_id"] == "github:admin"

    def test_assign_roles_empty_list(self, client, mock_auth_service, admin_token):
        """Test that empty role list is rejected."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:admin",
            "email": "admin@example.com",
            "roles": ["admin"],
        }

        response = client.post(
            "/admin/users/github:123/roles", headers={"Authorization": f"Bearer {admin_token}"}, json={"roles": []}
        )

        # Should fail validation
        assert response.status_code == 422

    def test_assign_roles_user_not_found(self, client, mock_auth_service, admin_token):
        """Test assigning roles to non-existent user."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:admin",
            "email": "admin@example.com",
            "roles": ["admin"],
        }

        mock_auth_service.role_store.assign_roles.side_effect = ValueError("User record not found")

        response = client.post(
            "/admin/users/github:999/roles",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"roles": ["contributor"]},
        )

        assert response.status_code == 404

    def test_assign_roles_no_admin(self, client, mock_auth_service, non_admin_token):
        """Test that non-admin users cannot assign roles."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:user",
            "email": "user@example.com",
            "roles": ["contributor"],
        }

        response = client.post(
            "/admin/users/github:123/roles",
            headers={"Authorization": f"Bearer {non_admin_token}"},
            json={"roles": ["admin"]},
        )

        assert response.status_code == 403


class TestRevokeUserRoles:
    """Test DELETE /admin/users/{user_id}/roles endpoint."""

    def test_revoke_roles_success(self, client, mock_auth_service, admin_token):
        """Test successfully revoking roles as admin."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:admin",
            "email": "admin@example.com",
            "roles": ["admin"],
        }

        updated_record = {
            "user_id": "github:123",
            "roles": ["contributor"],
            "status": "approved",
            "last_modified_by": "github:admin",
        }
        mock_auth_service.role_store.revoke_roles.return_value = updated_record

        response = client.request(
            "DELETE",
            "/admin/users/github:123/roles",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json",
            },
            content=json.dumps({"roles": ["reviewer"]}),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["roles"] == ["contributor"]

        # Verify role store was called correctly
        mock_auth_service.role_store.revoke_roles.assert_called_once()
        call_kwargs = mock_auth_service.role_store.revoke_roles.call_args[1]
        assert call_kwargs["user_id"] == "github:123"
        assert call_kwargs["roles"] == ["reviewer"]
        assert call_kwargs["admin_user_id"] == "github:admin"

    def test_revoke_roles_user_not_found(self, client, mock_auth_service, admin_token):
        """Test revoking roles from non-existent user."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:admin",
            "email": "admin@example.com",
            "roles": ["admin"],
        }

        mock_auth_service.role_store.revoke_roles.side_effect = ValueError("User record not found")

        response = client.request(
            "DELETE",
            "/admin/users/github:999/roles",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json",
            },
            content=json.dumps({"roles": ["admin"]}),
        )

        assert response.status_code == 404

    def test_revoke_roles_no_admin(self, client, mock_auth_service, non_admin_token):
        """Test that non-admin users cannot revoke roles."""
        mock_auth_service.validate_token.return_value = {
            "sub": "github:user",
            "email": "user@example.com",
            "roles": ["contributor"],
        }

        response = client.request(
            "DELETE",
            "/admin/users/github:123/roles",
            headers={
                "Authorization": f"Bearer {non_admin_token}",
                "Content-Type": "application/json",
            },
            content=json.dumps({"roles": ["contributor"]}),
        )

        assert response.status_code == 403
