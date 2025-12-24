# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Config Registry service implementation."""

import json
from datetime import datetime
from typing import Any

from copilot_events import EventPublisher
from copilot_logging import StructuredLogger
from copilot_storage import DocumentStore

from .models import ConfigDiff, ConfigDocument, ConfigNotification


class ConfigRegistryService:
    """Centralized configuration registry service.

    Manages configuration documents for all services with:
    - Versioning and history tracking
    - Environment-specific overlays
    - Change notifications via event bus
    - Configuration diffing
    """

    def __init__(
        self,
        doc_store: DocumentStore,
        event_publisher: EventPublisher | None = None,
        logger: StructuredLogger | None = None,
    ):
        """Initialize config registry service.

        Args:
            doc_store: Document store for config persistence
            event_publisher: Optional event publisher for notifications
            logger: Optional logger instance
        """
        self.doc_store = doc_store
        self.event_publisher = event_publisher
        self.logger = logger
        self._stats = {
            "configs_created": 0,
            "configs_updated": 0,
            "configs_retrieved": 0,
            "configs_deleted": 0,
            "notifications_sent": 0,
        }

    def get_config(
        self, service_name: str, environment: str = "default", version: int | None = None
    ) -> dict[str, Any] | None:
        """Get configuration for a service.

        Args:
            service_name: Service name
            environment: Environment name (default, dev, staging, prod)
            version: Optional specific version (defaults to latest)

        Returns:
            Configuration data or None if not found
        """
        query = {"service_name": service_name, "environment": environment}

        if version is not None:
            query["version"] = version
            doc = self.doc_store.get_document("configs", query)
            if doc:
                self._stats["configs_retrieved"] += 1
                return doc.get("config_data")
        else:
            # Get latest version
            docs = self.doc_store.query_documents(
                "configs", query, sort=[("version", -1)], limit=1
            )
            if docs:
                self._stats["configs_retrieved"] += 1
                return docs[0].get("config_data")

        return None

    def create_config(
        self,
        service_name: str,
        config_data: dict[str, Any],
        environment: str = "default",
        created_by: str = "system",
        comment: str = "",
    ) -> ConfigDocument:
        """Create a new configuration.

        Args:
            service_name: Service name
            config_data: Configuration data
            environment: Environment name
            created_by: User creating the config
            comment: Change comment

        Returns:
            Created configuration document
        """
        # Check if config already exists
        existing = self.get_config(service_name, environment)
        if existing:
            raise ValueError(
                f"Configuration for {service_name}/{environment} already exists. Use update instead."
            )

        doc = ConfigDocument(
            service_name=service_name,
            environment=environment,
            version=1,
            config_data=config_data,
            created_by=created_by,
            comment=comment or "Initial configuration",
        )

        self.doc_store.insert_document("configs", doc.model_dump())
        self._stats["configs_created"] += 1

        # Send notification
        self._send_notification(service_name, environment, 1, "created", comment)

        if self.logger:
            self.logger.info(
                "config_created",
                service_name=service_name,
                environment=environment,
                version=1,
                created_by=created_by,
            )

        return doc

    def update_config(
        self,
        service_name: str,
        config_data: dict[str, Any],
        environment: str = "default",
        created_by: str = "system",
        comment: str = "",
    ) -> ConfigDocument:
        """Update configuration (creates new version).

        Args:
            service_name: Service name
            config_data: New configuration data
            environment: Environment name
            created_by: User updating the config
            comment: Change comment

        Returns:
            Updated configuration document
        """
        # Get latest version
        query = {"service_name": service_name, "environment": environment}
        docs = self.doc_store.query_documents(
            "configs", query, sort=[("version", -1)], limit=1
        )

        if not docs:
            raise ValueError(
                f"Configuration for {service_name}/{environment} does not exist. Use create instead."
            )

        latest_version = docs[0].get("version", 0)
        new_version = latest_version + 1

        doc = ConfigDocument(
            service_name=service_name,
            environment=environment,
            version=new_version,
            config_data=config_data,
            created_by=created_by,
            comment=comment or f"Updated to version {new_version}",
        )

        self.doc_store.insert_document("configs", doc.model_dump())
        self._stats["configs_updated"] += 1

        # Send notification
        self._send_notification(service_name, environment, new_version, "updated", comment)

        if self.logger:
            self.logger.info(
                "config_updated",
                service_name=service_name,
                environment=environment,
                old_version=latest_version,
                new_version=new_version,
                created_by=created_by,
            )

        return doc

    def list_configs(
        self, service_name: str | None = None, environment: str | None = None
    ) -> list[dict[str, Any]]:
        """List all configurations.

        Args:
            service_name: Optional service name filter
            environment: Optional environment filter

        Returns:
            List of configuration documents
        """
        query = {}
        if service_name:
            query["service_name"] = service_name
        if environment:
            query["environment"] = environment

        # Get latest versions only
        pipeline = [
            {"$match": query} if query else {"$match": {}},
            {"$sort": {"version": -1}},
            {
                "$group": {
                    "_id": {"service_name": "$service_name", "environment": "$environment"},
                    "latest": {"$first": "$$ROOT"},
                }
            },
            {"$replaceRoot": {"newRoot": "$latest"}},
        ]

        docs = list(self.doc_store.doc_store.db["configs"].aggregate(pipeline))
        return docs

    def get_config_history(
        self, service_name: str, environment: str = "default", limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get configuration history.

        Args:
            service_name: Service name
            environment: Environment name
            limit: Maximum number of versions to return

        Returns:
            List of configuration versions (newest first)
        """
        query = {"service_name": service_name, "environment": environment}
        docs = self.doc_store.query_documents(
            "configs", query, sort=[("version", -1)], limit=limit
        )
        return docs

    def diff_configs(
        self,
        service_name: str,
        environment: str = "default",
        old_version: int | None = None,
        new_version: int | None = None,
    ) -> ConfigDiff:
        """Compare two configuration versions.

        Args:
            service_name: Service name
            environment: Environment name
            old_version: Old version number (defaults to latest - 1)
            new_version: New version number (defaults to latest)

        Returns:
            Configuration diff
        """
        # Get versions
        history = self.get_config_history(service_name, environment, limit=2)
        if len(history) < 2 and (old_version is None or new_version is None):
            raise ValueError("Not enough versions to compare")

        if new_version is None:
            new_doc = history[0]
            new_version = new_doc["version"]
        else:
            new_doc = self.doc_store.get_document(
                "configs",
                {"service_name": service_name, "environment": environment, "version": new_version},
            )
            if not new_doc:
                raise ValueError(f"Version {new_version} not found")

        if old_version is None:
            old_doc = history[1] if len(history) > 1 else {}
            old_version = old_doc.get("version", 0)
        else:
            old_doc = self.doc_store.get_document(
                "configs",
                {"service_name": service_name, "environment": environment, "version": old_version},
            )
            if not old_doc:
                raise ValueError(f"Version {old_version} not found")

        old_data = old_doc.get("config_data", {})
        new_data = new_doc.get("config_data", {})

        # Calculate diff
        added = {k: v for k, v in new_data.items() if k not in old_data}
        removed = {k: v for k, v in old_data.items() if k not in new_data}
        changed = {
            k: {"old": old_data[k], "new": new_data[k]}
            for k in old_data
            if k in new_data and old_data[k] != new_data[k]
        }

        return ConfigDiff(
            service_name=service_name,
            environment=environment,
            old_version=old_version,
            new_version=new_version,
            added=added,
            removed=removed,
            changed=changed,
        )

    def delete_config(
        self, service_name: str, environment: str = "default", version: int | None = None
    ) -> int:
        """Delete configuration(s).

        Args:
            service_name: Service name
            environment: Environment name
            version: Optional specific version (if None, deletes all versions)

        Returns:
            Number of documents deleted
        """
        query = {"service_name": service_name, "environment": environment}
        if version is not None:
            query["version"] = version

        count = self.doc_store.delete_documents("configs", query)
        self._stats["configs_deleted"] += count

        # Send notification
        self._send_notification(
            service_name, environment, version or 0, "deleted", "Configuration deleted"
        )

        if self.logger:
            self.logger.info(
                "config_deleted",
                service_name=service_name,
                environment=environment,
                version=version,
                count=count,
            )

        return count

    def _send_notification(
        self,
        service_name: str,
        environment: str,
        version: int,
        change_type: str,
        comment: str,
    ) -> None:
        """Send config change notification.

        Args:
            service_name: Service name
            environment: Environment name
            version: Config version
            change_type: Type of change (created, updated, deleted)
            comment: Change comment
        """
        if not self.event_publisher:
            return

        notification = ConfigNotification(
            service_name=service_name,
            environment=environment,
            version=version,
            change_type=change_type,
            comment=comment,
        )

        try:
            self.event_publisher.publish(
                "config.changes", notification.model_dump(), routing_key=f"config.{change_type}"
            )
            self._stats["notifications_sent"] += 1
        except Exception as e:
            if self.logger:
                self.logger.error("notification_failed", error=str(e))

    def get_stats(self) -> dict[str, int]:
        """Get service statistics.

        Returns:
            Dictionary of statistics
        """
        return self._stats.copy()
