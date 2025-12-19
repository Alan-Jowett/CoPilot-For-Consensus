# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Role storage and retrieval backed by copilot_storage.

This module persists user role assignments in a document store (default MongoDB)
via the shared copilot_storage adapter. It supports creating pending records for
new users and optional auto-approval into default roles.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple

from copilot_auth.models import User
from copilot_auth.provider import AuthenticationError
from copilot_logging import create_logger
from copilot_schema_validation import FileSchemaProvider
from copilot_storage import DocumentStore, create_document_store
from copilot_storage.validating_document_store import ValidatingDocumentStore


logger = create_logger(logger_type="stdout", level="INFO", name="auth.role_store")


class RoleStore:
    """Persist and retrieve user role assignments."""

    def __init__(self, config: object):
        self.collection = getattr(config, "role_store_collection", "user_roles")

        store_kwargs = {
            "host": getattr(config, "role_store_host", None),
            "port": getattr(config, "role_store_port", None),
            "username": getattr(config, "role_store_username", None),
            "password": getattr(config, "role_store_password", None),
            "database": getattr(config, "role_store_database", "auth"),
        }

        # Drop keys that are None to allow copilot_storage env defaults
        store_kwargs = {k: v for k, v in store_kwargs.items() if v is not None}

        base_store: DocumentStore = create_document_store(
            store_type=getattr(config, "role_store_type", "mongodb"),
            **store_kwargs,
        )

        schema_dir = getattr(config, "role_store_schema_dir", None)
        if schema_dir is None:
            # Default to repository schema location
            schema_dir = (
                Path(__file__).resolve().parents[1]
                / "documents"
                / "schemas"
                / "role_store"
            )

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
    ) -> Tuple[List[str], str]:
        """Fetch or create role assignment for a user.

        Returns a tuple of (roles, status) where status is one of
        "approved", "pending", or "denied".
        """

        record = self._find_user_record(user.id)

        if record:
            status = record.get("status", "pending")
            roles = record.get("roles", []) or []

            if status == "denied":
                return [], status
            return roles, status

        # No record -> create one
        roles: List[str] = []
        status = "pending"

        auto_roles = [r for r in auto_approve_roles if r]
        if auto_approve_enabled and auto_roles:
            roles = auto_roles
            status = "approved"

        self._insert_user_record(user=user, roles=roles, status=status)
        return roles, status

    def _find_user_record(self, user_id: str):
        docs = self.store.query_documents(self.collection, {"user_id": user_id}, limit=1)
        return docs[0] if docs else None

    def _insert_user_record(self, user: User, roles: List[str], status: str) -> None:
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
            logger.error("Failed to insert user role record: %s", exc)
            raise AuthenticationError("Could not persist role assignment") from exc
