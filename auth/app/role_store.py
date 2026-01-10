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
from copilot_schema_validation import create_schema_provider
from copilot_storage import DocumentStore, create_document_store

logger = create_logger("stdout", {"level": "INFO", "name": "auth.role_store"})


class RoleStore:
    """Persist and retrieve user role assignments."""

    # Valid roles that can be assigned
    # This is a security measure to prevent arbitrary role assignment
    VALID_ROLES = {"admin", "contributor", "reviewer", "reader"}

    def __init__(self, config: object):
        self.collection = config.role_store_collection

        document_store_adapter = None
        get_adapter = getattr(config, "get_adapter", None)
        if callable(get_adapter):
            document_store_adapter = get_adapter("document_store")

        driver_name = getattr(document_store_adapter, "driver_name", None) if document_store_adapter else None
        driver_config = (
            getattr(getattr(document_store_adapter, "driver_config", None), "config", None)
            if document_store_adapter
            else None
        )
        if not isinstance(driver_config, dict):
            driver_config = {}

        driver_config = dict(driver_config)

        if not driver_name:
            driver_name = "inmemory"

        schema_dir = getattr(config, "role_store_schema_dir", None)
        if schema_dir is None:
            # Try to find schema directory relative to this file
            # In container: /app/app/role_store.py -> parents[1] is /app
            # Locally: .../auth/app/role_store.py -> parents[1] is .../auth
            # Check both locations
            local_candidate = Path(__file__).resolve().parents[1].parent / "docs" / "schemas" / "role_store"
            if local_candidate.exists():
                schema_dir = local_candidate
            else:
                # Fallback: assume we're in the repo and go up to find docs
                schema_dir = Path(__file__).resolve().parents[1] / "docs" / "schemas" / "role_store"

        schema_provider = create_schema_provider(schema_dir=str(schema_dir))
        driver_config["schema_provider"] = schema_provider

        self.store = create_document_store(
            driver_name=driver_name,
            driver_config=driver_config,
            enable_validation=True,
            strict_validation=True,
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
        first_user_auto_promotion_enabled: bool = False,
    ) -> tuple[list[str], str]:
        """Fetch or create role assignment for a user.

        Returns a tuple of (roles, status) where status is one of
        "approved", "pending", or "denied".

        Special behavior: If this is a NEW USER (no existing record) and no admins exist
        in the system and auto-promotion is enabled (first_user_auto_promotion_enabled=True),
        the user is automatically promoted to admin. This is disabled by default for production
        security. Existing users with records are never affected by this setting.

        Args:
            user: User object with id, email, name
            auto_approve_enabled: Whether to auto-approve new users with default roles
            auto_approve_roles: List of roles to assign when auto-approving
            first_user_auto_promotion_enabled: If True, enables auto-promotion of first user
                to admin. Disabled by default (False) for production security. Set to True
                only in development/testing environments.
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
        # Only if explicitly enabled (disabled by default for production security)
        # Admin users also get reader role for basic access to reporting endpoints
        if first_user_auto_promotion_enabled:
            admins = self.find_by_role("admin")
            if not admins:
                roles = ["admin", "reader"]
                status = "approved"
                logger.info(f"Auto-promoting first user {user.id} to admin and reader roles (no admins exist)")

        # If auto-promotion didn't happen, check normal auto-approval
        if not roles:
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
            valid_roles_str = ", ".join(sorted(self.VALID_ROLES))
            raise ValueError(f"Invalid roles: {', '.join(invalid_roles)}. " f"Valid roles are: {valid_roles_str}")

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
                # Update using the document's _id if available
                if "_id" in record:
                    # Remove _id from the update doc (don't pass it to validation)
                    update_doc = {k: v for k, v in updated_doc.items() if k != "_id"}
                    self.store.update_document(self.collection, record["_id"], update_doc)
                else:
                    # If no _id (new record), insert it
                    insert_doc = {k: v for k, v in updated_doc.items() if k != "_id"}
                    self.store.insert_document(self.collection, insert_doc)
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
            raise

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
            valid_roles_str = ", ".join(sorted(self.VALID_ROLES))
            raise ValueError(f"Invalid roles: {', '.join(invalid_roles)}. " f"Valid roles are: {valid_roles_str}")

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
            # Try to update document
            # Remove _id from the update doc (MongoDB doesn't allow updating immutable _id field)
            update_doc = {k: v for k, v in updated_doc.items() if k != "_id"}

            if "_id" in record:
                # Update using the document's _id
                self.store.update_document(self.collection, record["_id"], update_doc)
            else:
                # If no _id, try to update with query filter (may not work with all stores)
                # This is a fallback for stores that support filter-based updates
                from copilot_storage.document_store import DocumentNotFoundError

                try:
                    self.store.update_document(self.collection, {"user_id": user_id}, update_doc)
                except (DocumentNotFoundError, TypeError):
                    # If update by query fails, this store requires _id
                    # Shouldn't happen since record came from _find_user_record which queries
                    raise ValueError(f"Cannot update document for user {user_id} without _id")

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

    def search_users(
        self,
        search_term: str,
        search_by: str = "user_id",
    ) -> list[dict[str, Any]]:
        """Search for users by various fields.

        Args:
            search_term: The search term to look for
            search_by: Field to search by ('user_id', 'email', 'name')

        Returns:
            List of matching user role records

        Raises:
            ValueError: If search_by field is invalid
        """
        valid_fields = {"user_id", "email", "name"}
        if search_by not in valid_fields:
            raise ValueError(f"Invalid search_by field: {search_by}. Must be one of {valid_fields}")

        try:
            # For user_id, do exact match
            if search_by == "user_id":
                docs = self.store.query_documents(self.collection, {"user_id": search_term})
            else:
                # For email and name, we need to handle case-insensitive partial matching
                # Since copilot_storage doesn't support regex queries directly,
                # we'll fetch all documents and filter in memory
                # This is not ideal for large datasets, but works for MVP
                all_docs = self.store.query_documents(self.collection, {})
                search_lower = search_term.lower()
                docs = [
                    doc for doc in all_docs if doc.get(search_by) and search_lower in doc.get(search_by, "").lower()
                ]

            return docs
        except Exception as exc:
            logger.error(f"Failed to search users by {search_by}={search_term}: {exc}")
            return []
