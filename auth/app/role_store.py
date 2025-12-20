# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Role storage and retrieval backed by copilot_storage.

This module persists user role assignments in a document store (default MongoDB)
via the shared copilot_storage adapter. It supports creating pending records for
new users and optional auto-approval into default roles.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from copilot_auth.models import User
from copilot_auth.provider import AuthenticationError
from copilot_logging import create_logger
from copilot_schema_validation import FileSchemaProvider
from copilot_storage import DocumentStore, create_document_store
from copilot_storage.validating_document_store import ValidatingDocumentStore

logger = create_logger(logger_type="stdout", level="INFO", name="auth.role_store")


class RoleStore:
    """Persist and retrieve user role assignments."""

    # Valid roles that can be assigned
    # This is a security measure to prevent arbitrary role assignment
    VALID_ROLES = {"admin", "contributor", "reviewer", "reader"}

    def __init__(self, config: object):
        self.collection = getattr(config, "role_store_collection", "user_roles")

        # Get values from config with fallback to environment variables
        # For password/username, read directly from Docker secrets if available
        import os
        
        # Helper to read from Docker secrets first, then environment variables
        def get_secret_or_env(secret_name: str, env_var: str) -> str | None:
            # Try reading from Docker secrets first (mounted at /run/secrets/)
            secret_file = f"/run/secrets/{secret_name}"
            if os.path.exists(secret_file):
                try:
                    with open(secret_file, 'r') as f:
                        content = f.read().strip()
                        if content:  # Only return if not empty
                            return content
                except Exception:
                    pass
            
            # Fallback to environment variable
            value = os.getenv(env_var)
            # Only return if it's not empty string
            return value if value else None
        
        store_kwargs = {
            "host": getattr(config, "role_store_host", None) or os.getenv("DOCUMENT_DATABASE_HOST"),
            "port": getattr(config, "role_store_port", None) or os.getenv("DOCUMENT_DATABASE_PORT"),
            "username": getattr(config, "role_store_username", None) or get_secret_or_env("document_database_user", "DOCUMENT_DATABASE_USER"),
            "password": getattr(config, "role_store_password", None) or get_secret_or_env("document_database_password", "DOCUMENT_DATABASE_PASSWORD"),
            "database": getattr(config, "role_store_database", None) or os.getenv("DOCUMENT_DATABASE_NAME", "auth"),
        }

        # Convert port to int if it's a string
        if store_kwargs.get("port") is not None:
            if isinstance(store_kwargs["port"], str):
                store_kwargs["port"] = int(store_kwargs["port"])

        # Drop keys that are None or 0 (for port) to allow copilot_storage env defaults
        store_kwargs = {k: v for k, v in store_kwargs.items() if v is not None and (k != "port" or v != 0)}

        base_store: DocumentStore = create_document_store(
            store_type=getattr(config, "role_store_type", "mongodb"),
            **store_kwargs,
        )

        schema_dir = getattr(config, "role_store_schema_dir", None)
        if schema_dir is None:
            # Default to repository schema location
            schema_dir = Path(__file__).resolve().parents[1] / "documents" / "schemas" / "role_store"

        schema_provider = FileSchemaProvider(Path(schema_dir))

        self.store: DocumentStore = ValidatingDocumentStore(
            store=base_store,
            schema_provider=schema_provider,
            strict=True,
            validate_reads=False,
        )

        connect = getattr(self.store, "connect", None)
        if callable(connect):
            connect()

    def get_roles_for_user(
        self,
        user: User,
        auto_approve_enabled: bool,
        auto_approve_roles: Iterable[str],
    ) -> tuple[list[str], str]:
        """Fetch or create role assignment for a user.

        Returns a tuple of (roles, status) where status is one of
        "approved", "pending", or "denied".
        
        Special behavior: If no admins exist in the system, the first user to log in
        is automatically promoted to admin.
        """

        record = self._find_user_record(user.id)

        if record:
            status = record.get("status", "pending")
            roles = record.get("roles", []) or []

            if status == "denied":
                return [], status
            return roles, status

        # No record -> create one
        roles: list[str] = []
        status = "pending"

        # Special case: auto-promote first user to admin if no admins exist
        admins = self.find_by_role("admin")
        if not admins:
            roles = ["admin"]
            status = "approved"
            logger.info(f"Auto-promoting first user {user.id} to admin role (no admins exist)")
        else:
            # Normal role assignment
            auto_roles = [r for r in auto_approve_roles if r]
            if auto_approve_enabled and auto_roles:
                roles = auto_roles
                status = "approved"

        self._insert_user_record(user=user, roles=roles, status=status)
        return roles, status

    def _find_user_record(self, user_id: str):
        docs = self.store.query_documents(self.collection, {"user_id": user_id}, limit=1)
        return docs[0] if docs else None

    def _insert_user_record(self, user: User, roles: list[str], status: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "user_id": user.id,
            "provider": user.id.split(":", 1)[0] if ":" in user.id else "unknown",
            "email": user.email,
            "name": user.name,
            "roles": roles,
            "status": status,
            "requested_at": now,
            "updated_at": now,
        }

        try:
            self.store.insert_document(self.collection, doc)
        except Exception as exc:  # pragma: no cover
            logger.exception(f"Failed to insert user role record: {exc}")
            raise AuthenticationError("Could not persist role assignment") from exc

    # Admin methods
    def list_pending_role_assignments(
        self,
        user_id: str | None = None,
        role: str | None = None,
        limit: int = 50,
        skip: int = 0,
        sort_by: str = "requested_at",
        sort_order: int = -1,
    ) -> tuple[list[dict[str, Any]], int]:
        """List pending role assignment requests with filtering and pagination.

        Args:
            user_id: Optional filter by user ID
            role: Optional filter by role (checks if role is in roles array)
            limit: Maximum number of results to return (default: 50)
            skip: Number of results to skip for pagination (default: 0)
            sort_by: Field to sort by (default: requested_at)
            sort_order: Sort order: -1 for descending, 1 for ascending (default: -1)

        Returns:
            Tuple of (list of pending assignments, total count)
        """
        query = {"status": "pending"}

        if user_id:
            query["user_id"] = user_id

        if role:
            query["roles"] = role

        try:
            # Get total count for pagination
            all_docs = self.store.query_documents(self.collection, query)
            total_count = len(all_docs)

            # Get paginated results with sorting
            # LIMITATION: copilot_storage doesn't expose sort/skip/limit directly,
            # so we implement it in-memory. This does not scale well for large datasets
            # and could cause performance issues or memory exhaustion in production.
            # For production use, consider implementing pagination at the database level
            # or using a store adapter that supports native pagination.
            sorted_docs = sorted(all_docs, key=lambda x: x.get(sort_by, ""), reverse=(sort_order == -1))
            paginated_docs = sorted_docs[skip : skip + limit]

            return paginated_docs, total_count

        except Exception as exc:
            logger.exception(f"Failed to list pending role assignments: {exc}")
            raise

    def get_user_roles(self, user_id: str) -> dict[str, Any] | None:
        """Get current roles assigned to a given user.

        Args:
            user_id: User identifier

        Returns:
            User role record or None if not found
        """
        return self._find_user_record(user_id)

    def assign_roles(
        self,
        user_id: str,
        roles: list[str],
        admin_user_id: str,
        admin_email: str | None = None,
    ) -> dict[str, Any]:
        """Assign roles to a user and update status to approved.

        Args:
            user_id: User identifier
            roles: List of roles to assign
            admin_user_id: ID of the admin performing the action
            admin_email: Email of the admin performing the action

        Returns:
            Updated user role record

        Raises:
            ValueError: If user record not found or invalid roles provided
        """
        # Validate roles
        invalid_roles = [r for r in roles if r not in self.VALID_ROLES]
        if invalid_roles:
            raise ValueError(f"Invalid roles: {', '.join(invalid_roles)}. Valid roles are: {', '.join(sorted(self.VALID_ROLES))}")

        record = self._find_user_record(user_id)

        if not record:
            # If user record doesn't exist, create a minimal one
            now = datetime.now(timezone.utc).isoformat()
            record = {
                "user_id": user_id,
                "roles": [],
                "status": "pending",
                "created_at": now,
            }

        now = datetime.now(timezone.utc).isoformat()

        # Merge new roles with existing roles (avoid duplicates)
        current_roles = record.get("roles", [])
        merged_roles = list(set(current_roles + roles))  # Combine and deduplicate
        merged_roles.sort()  # Sort for consistent ordering

        # Update roles and status
        updated_doc = {
            **record,
            "roles": merged_roles,
            "status": "approved",
            "updated_at": now,
            "approved_by": admin_user_id,
            "approved_at": now,
        }

        try:
            # Try to update, or insert if doesn't exist
            from copilot_storage.document_store import DocumentNotFoundError
            try:
                self.store.update_document(self.collection, {"user_id": user_id}, updated_doc)
            except DocumentNotFoundError:
                # Document doesn't exist, create it
                # Remove _id if present (MongoDB will generate a new one)
                insert_doc = {k: v for k, v in updated_doc.items() if k != "_id"}
                self.store.insert_document(self.collection, insert_doc)

            # Log audit event
            logger.info(
                f"Roles assigned to user {user_id} by admin {admin_user_id}",
                extra={
                    "event": "roles_assigned",
                    "user_id": user_id,
                    "roles": roles,
                    "admin_user_id": admin_user_id,
                    "admin_email": admin_email,
                    "timestamp": now,
                },
            )

            return updated_doc

        except Exception as exc:
            logger.exception(f"Failed to assign roles: {exc}")

    def revoke_roles(
        self,
        user_id: str,
        roles: list[str],
        admin_user_id: str,
        admin_email: str | None = None,
    ) -> dict[str, Any]:
        """Revoke roles from a user.

        Args:
            user_id: User identifier
            roles: List of roles to revoke
            admin_user_id: ID of the admin performing the action
            admin_email: Email of the admin performing the action

        Returns:
            Updated user role record

        Raises:
            ValueError: If user record not found or invalid roles provided
        """
        # Validate roles
        invalid_roles = [r for r in roles if r not in self.VALID_ROLES]
        if invalid_roles:
            raise ValueError(f"Invalid roles: {', '.join(invalid_roles)}. Valid roles are: {', '.join(sorted(self.VALID_ROLES))}")

        record = self._find_user_record(user_id)

        if not record:
            raise ValueError(f"User record not found: {user_id}")

        now = datetime.now(timezone.utc).isoformat()

        # Remove specified roles
        current_roles = record.get("roles", [])
        updated_roles = [r for r in current_roles if r not in roles]

        # Update document
        updated_doc = {
            **record,
            "roles": updated_roles,
            "updated_at": now,
            "last_modified_by": admin_user_id,
        }

        try:
            # Update document
            self.store.update_document(self.collection, {"user_id": user_id}, updated_doc)

            # Log audit event
            logger.info(
                f"Roles revoked from user {user_id} by admin {admin_user_id}",
                extra={
                    "event": "roles_revoked",
                    "user_id": user_id,
                    "revoked_roles": roles,
                    "remaining_roles": updated_roles,
                    "admin_user_id": admin_user_id,
                    "admin_email": admin_email,
                    "timestamp": now,
                },
            )

            return updated_doc

        except Exception as exc:
            logger.exception(f"Failed to revoke roles: {exc}")
            raise

    def find_by_role(self, role: str) -> list[dict[str, Any]]:
        """Find all users with a specific role.

        Args:
            role: The role to search for

        Returns:
            List of user role records containing the specified role
        """
        try:
            docs = self.store.query_documents(self.collection, {"roles": role})
            return docs
        except Exception as exc:
            logger.error(f"Failed to find users by role {role}: {exc}")
            return []