# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Blob Storage-based archive store implementation."""

import hashlib
import json
import logging
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from azure.core.exceptions import AzureError, ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContainerClient
from copilot_config.generated.adapters.archive_store import (
    DriverConfig_ArchiveStore_Azureblob,
    DriverConfig_ArchiveStore_Azureblob_AccountKey,
    DriverConfig_ArchiveStore_Azureblob_ConnectionString,
    DriverConfig_ArchiveStore_Azureblob_ManagedIdentity,
    DriverConfig_ArchiveStore_Azureblob_SasToken,
)

from .archive_store import (
    ArchiveStore,
    ArchiveStoreConnectionError,
    ArchiveStoreError,
)

logger = logging.getLogger(__name__)


class AzureBlobArchiveStore(ArchiveStore):
    """Azure Blob Storage-based archive storage.

    This implementation stores archives in Azure Blob Storage, enabling
    cloud-native deployments with scalability and high availability.

    Configuration is via environment variables:
    - AZURE_STORAGE_ACCOUNT: Storage account name
    - AZURE_STORAGE_KEY: Storage account key (primary or secondary)
    - AZURE_STORAGE_SAS_TOKEN: SAS token (alternative to key, without leading '?')
    - AZURE_STORAGE_CONTAINER: Container name for archives
    - AZURE_STORAGE_PREFIX: Optional path prefix for organizing blobs

    Storage Strategy:
    - Archives are stored as blobs organized by source_name/filename
    - Content-addressable IDs enable deduplication at the metadata level
    - Same content stored multiple times reuses the same archive_id but creates
      separate blobs to maintain source/filename context
    - A central JSON metadata blob provides efficient listing and querying

    Performance Considerations:
    - Metadata index is loaded into memory on initialization for fast access
    - Hash index provides O(1) content hash lookups
    - For very large deployments (millions of archives), consider using
      Azure Table Storage or Cosmos DB for metadata indexing
    - ETag-based optimistic concurrency prevents lost updates in multi-instance deployments
    """

    def __init__(
        self,
        account_name: str | None = None,
        account_key: str | None = None,
        sas_token: str | None = None,
        container_name: str | None = None,
        prefix: str | None = None,
        connection_string: str | None = None,
    ):
        """Initialize Azure Blob archive store.

        Supports two authentication modes:
        1. Connection String: Pass connection_string parameter (simplest, includes credentials)
        2. Managed Identity: Pass account_name only (no credentials; uses Azure credentials)

        Args:
            connection_string: Full Azure Storage connection string.
                             Either connection_string OR account_name must be provided, but not both.
            account_name: Azure storage account name.
                         Use with managed identity (no account_key or sas_token) or with credentials.
                         Either connection_string OR account_name must be provided, but not both.
            account_key: Storage account key (requires account_name).
                        Incompatible with connection_string.
            sas_token: SAS token as credential (requires account_name).
                      Incompatible with connection_string and account_key.
            container_name: Container name for archives (default: "raw-archives").
            prefix: Optional path prefix for organizing blobs (default: empty string).

        Raises:
            ValueError: If configuration is inconsistent or incomplete
        """
        # Use caller-provided configuration only (no environment fallbacks)
        self.account_name = account_name
        self.account_key = account_key
        self.sas_token = sas_token
        self.container_name = container_name or "raw-archives"
        self.prefix = prefix or ""
        self.connection_string = connection_string

        # Ensure prefix ends with / if provided
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"

        # Validate authentication configuration: must use EITHER connection_string OR account_name, not both or neither
        has_connection_string = bool(self.connection_string)
        has_account_name = bool(self.account_name)

        if has_connection_string and has_account_name:
            raise ValueError(
                "Cannot provide both connection_string and account_name. "
                "Choose one authentication method: "
                "1) connection_string (includes embedded credentials), or "
                "2) account_name (with managed identity or explicit credentials)"
            )

        if not has_connection_string and not has_account_name:
            raise ValueError(
                "Authentication configuration required. Provide either: "
                "1) connection_string (full connection string), or "
                "2) account_name (with managed identity or account_key/sas_token)"
            )

        # If using account_name, validate credentials are not mixed
        if has_account_name:
            if self.account_key and self.sas_token:
                raise ValueError(
                    "Cannot provide both account_key and sas_token. "
                    "Choose one credential method: account_key or sas_token (or neither for managed identity)"
                )

        # If using connection_string, ensure no conflicting credentials (account_name already excluded above)
        if has_connection_string:
            if self.account_key or self.sas_token:
                raise ValueError(
                    "Cannot provide account_key or sas_token when using connection_string. "
                    "Use only connection_string for connection string authentication"
                )

        # Initialize Azure Blob Service Client
        try:
            if self.connection_string:
                # Connection string authentication (includes embedded credentials)
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            elif self.sas_token:
                # SAS token authentication
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                self.blob_service_client = BlobServiceClient(
                    account_url=account_url, credential=self.sas_token
                )
            elif self.account_key:
                # Account key authentication
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                self.blob_service_client = BlobServiceClient(
                    account_url=account_url, credential=self.account_key
                )
            else:
                # Managed identity authentication (no explicit credentials; uses DefaultAzureCredential)
                try:
                    from azure.identity import DefaultAzureCredential
                except ImportError as e:
                    raise ImportError(
                        "azure-identity is required for managed identity authentication. "
                        "Install with: pip install azure-identity"
                    ) from e

                account_url = f"https://{self.account_name}.blob.core.windows.net"
                credential = DefaultAzureCredential()
                self.blob_service_client = BlobServiceClient(
                    account_url=account_url, credential=credential
                )

            # Get container client (create if not exists)
            self.container_client: ContainerClient = (
                self.blob_service_client.get_container_client(self.container_name)
            )

            # Create container if it doesn't exist
            try:
                self.container_client.create_container()
                logger.info("Created container: %s", self.container_name)
            except ResourceExistsError:
                # Container already exists; nothing to do
                pass
            except AzureError as exc:
                # Surface unexpected Azure errors with clear context and preserve cause
                raise ArchiveStoreConnectionError(
                    f"Unexpected Azure error while creating container "
                    f"'{self.container_name}': {exc}"
                ) from exc

        except ArchiveStoreConnectionError:
            # Preserve detailed connection errors raised above
            raise
        except Exception as exc:
            # Wrap any other initialization failures in ArchiveStoreConnectionError
            raise ArchiveStoreConnectionError(
                f"Failed to initialize Azure Blob Archive Store: {exc}"
            ) from exc

        # Metadata index blob name
        self.metadata_blob_name = f"{self.prefix}metadata/archives_index.json"

        # Load metadata index and store ETag for concurrency control
        self._metadata: dict[str, dict[str, Any]] = {}
        self._metadata_etag: str | None = None
        self._hash_index: dict[str, str] = {}  # content_hash -> archive_id mapping
        self._load_metadata()

    @classmethod
    def from_config(
        cls, driver_config: DriverConfig_ArchiveStore_Azureblob
    ) -> "AzureBlobArchiveStore":
        """Create AzureBlobArchiveStore from typed driver config.

        Args:
            driver_config: DriverConfig object containing archive store configuration
                          Expected keys: connection_string OR account_name, plus optional
                          account_key, sas_token, container_name, prefix

        Returns:
            AzureBlobArchiveStore instance

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        container_name = driver_config.azureblob_container_name or "archives"
        prefix = driver_config.azureblob_prefix or ""

        if isinstance(driver_config, DriverConfig_ArchiveStore_Azureblob_ConnectionString):
            return cls(
                connection_string=driver_config.azureblob_connection_string,
                container_name=container_name,
                prefix=prefix,
            )

        if isinstance(driver_config, DriverConfig_ArchiveStore_Azureblob_AccountKey):
            return cls(
                account_name=driver_config.azureblob_account_name,
                account_key=driver_config.azureblob_account_key,
                container_name=container_name,
                prefix=prefix,
            )

        if isinstance(driver_config, DriverConfig_ArchiveStore_Azureblob_SasToken):
            return cls(
                account_name=driver_config.azureblob_account_name,
                sas_token=driver_config.azureblob_sas_token,
                container_name=container_name,
                prefix=prefix,
            )

        if isinstance(driver_config, DriverConfig_ArchiveStore_Azureblob_ManagedIdentity):
            return cls(
                account_name=driver_config.azureblob_account_name,
                container_name=container_name,
                prefix=prefix,
            )

        raise ValueError(f"Unsupported azureblob driver config type: {type(driver_config)}")

    def _load_metadata(self) -> None:
        """Load metadata index from Azure Blob Storage."""
        try:
            blob_client = self.container_client.get_blob_client(self.metadata_blob_name)
            download_stream = blob_client.download_blob()
            metadata_json = download_stream.readall().decode("utf-8")
            self._metadata = json.loads(metadata_json)
            # Store ETag for optimistic concurrency control
            self._metadata_etag = download_stream.properties.etag
            # Build hash index for O(1) lookups
            self._hash_index = {
                metadata["content_hash"]: archive_id
                for archive_id, metadata in self._metadata.items()
                if "content_hash" in metadata
            }
            logger.debug("Loaded metadata index with %d entries", len(self._metadata))
        except ResourceNotFoundError:
            # Metadata blob doesn't exist yet (first run)
            self._metadata = {}
            self._metadata_etag = None
            self._hash_index = {}
            logger.info("No existing metadata index found, starting fresh")
        except Exception as e:
            # Start with empty metadata if load fails
            self._metadata = {}
            self._metadata_etag = None
            self._hash_index = {}
            logger.warning("Failed to load archive metadata: %s", e)

    def _save_metadata(self) -> None:
        """Save metadata index to Azure Blob Storage with optimistic concurrency control.

        Uses ETag-based optimistic concurrency to prevent lost updates when multiple
        instances write simultaneously. If a conflict is detected, the operation fails
        and the caller should reload metadata and retry.

        ETag Refresh Strategy:
        - For optimal performance, ETags are extracted from the upload_blob result when available
        - Azure SDK versions may return ETags as a result attribute (hasattr check) or as dict key
        - If neither is available, falls back to get_blob_properties() to fetch fresh metadata
        - The fallback incurs an extra network round-trip but ensures correctness for SDK versions
          that don't include ETags in the upload response
        """
        from azure.core import MatchConditions

        try:
            metadata_json = json.dumps(self._metadata, indent=2)
            blob_client = self.container_client.get_blob_client(self.metadata_blob_name)

            # Use ETag for optimistic concurrency control
            if self._metadata_etag:
                result = blob_client.upload_blob(
                    metadata_json.encode("utf-8"),
                    overwrite=True,
                    etag=self._metadata_etag,
                    match_condition=MatchConditions.IfNotModified
                )
            else:
                result = blob_client.upload_blob(
                    metadata_json.encode("utf-8"), overwrite=True
                )

            # Refresh stored ETag from upload response when available, otherwise fall back to a properties call.
            # Azure SDK versions differ: sometimes an object attribute, sometimes a mapping key.
            etag: str | None = None
            etag_attr = getattr(result, "etag", None)
            if isinstance(etag_attr, str) and etag_attr:
                etag = etag_attr
            elif isinstance(result, Mapping):
                etag_key = result.get("etag")
                if isinstance(etag_key, str) and etag_key:
                    etag = etag_key

            if etag is not None:
                self._metadata_etag = etag
            else:
                # Best-effort ETag refresh: metadata has already been uploaded successfully.
                try:
                    properties = blob_client.get_blob_properties()
                    self._metadata_etag = properties.etag
                except AzureError as refresh_error:
                    # Do not fail the save operation if the ETag refresh fails; log for observability instead.
                    logger.warning(
                        "Metadata saved, but failed to refresh ETag from blob properties: %s",
                        refresh_error,
                    )
                    self._metadata_etag = None
            logger.debug("Saved metadata index with %d entries", len(self._metadata))
        except Exception as e:
            raise ArchiveStoreError(f"Failed to save metadata: {e}") from e

    def _calculate_hash(self, content: bytes) -> str:
        """Calculate SHA256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    def _get_blob_name(self, source_name: str, filename: str) -> str:
        """Generate blob name for archive."""
        return f"{self.prefix}{source_name}/{filename}"

    def store_archive(self, source_name: str, file_path: str, content: bytes) -> str:
        """Store archive content in Azure Blob Storage.

        Args:
            source_name: Name of the source
            file_path: Original file path or name
            content: Raw archive content

        Returns:
            Archive ID (first 16 chars of content hash)

        Raises:
            ArchiveStoreError: If storage operation fails
        """
        try:
            # Calculate content hash for deduplication and ID generation
            content_hash = self._calculate_hash(content)
            archive_id = content_hash[:16]

            # Extract filename from file_path
            filename = os.path.basename(file_path)

            # Generate blob name
            blob_name = self._get_blob_name(source_name, filename)

            # Store blob with metadata
            blob_client = self.container_client.get_blob_client(blob_name)

            blob_metadata = {
                "archive_id": archive_id,
                "source_name": source_name,
                "original_path": file_path,
                "content_hash": content_hash,
            }

            blob_client.upload_blob(
                content,
                overwrite=True,
                metadata=blob_metadata
            )

            # Update metadata index and hash index
            self._metadata[archive_id] = {
                "archive_id": archive_id,
                "source_name": source_name,
                "blob_name": blob_name,
                "original_path": file_path,
                "content_hash": content_hash,
                "size_bytes": len(content),
                "stored_at": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
            }
            self._hash_index[content_hash] = archive_id
            self._save_metadata()

            logger.info("Stored archive %s for %s", archive_id, source_name)
            return archive_id

        except AzureError as e:
            raise ArchiveStoreError(f"Failed to store archive in Azure: {e}") from e
        except Exception as e:
            raise ArchiveStoreError(f"Failed to store archive: {e}") from e

    def get_archive(self, archive_id: str) -> bytes | None:
        """Retrieve archive content from Azure Blob Storage.

        Args:
            archive_id: Unique archive identifier

        Returns:
            Archive content as bytes, or None if not found

        Raises:
            ArchiveStoreError: If retrieval operation fails
        """
        try:
            metadata = self._metadata.get(archive_id)
            if not metadata:
                # Metadata is cached in-memory and can become stale in long-lived
                # services (e.g., Azure Container Apps) where ingestion updates the
                # metadata index after this instance started. Reload on miss.
                self._load_metadata()
                metadata = self._metadata.get(archive_id)
                if not metadata:
                    return None

            blob_name = metadata["blob_name"]
            blob_client = self.container_client.get_blob_client(blob_name)

            try:
                download_stream = blob_client.download_blob()
                content = download_stream.readall()
                logger.debug("Retrieved archive %s", archive_id)
                return content
            except ResourceNotFoundError:
                # Metadata exists but blob is missing
                logger.warning("Archive %s metadata exists but blob not found", archive_id)
                return None

        except AzureError as e:
            raise ArchiveStoreError(f"Failed to retrieve archive from Azure: {e}") from e
        except Exception as e:
            raise ArchiveStoreError(f"Failed to retrieve archive: {e}") from e

    def get_archive_by_hash(self, content_hash: str) -> str | None:
        """Retrieve archive ID by content hash for deduplication.

        Uses an in-memory hash index for O(1) lookup performance.

        Args:
            content_hash: SHA256 hash of the archive content

        Returns:
            Archive ID if found, None otherwise

        Raises:
            ArchiveStoreError: If query operation fails
        """
        archive_id = self._hash_index.get(content_hash)
        if archive_id is not None:
            return archive_id

        # Reload metadata once to avoid stale cache issues in long-lived services.
        self._load_metadata()
        return self._hash_index.get(content_hash)

    def archive_exists(self, archive_id: str) -> bool:
        """Check if archive exists in Azure Blob Storage.

        Args:
            archive_id: Unique archive identifier

        Returns:
            True if archive exists (both metadata and blob), False otherwise

        Raises:
            ArchiveStoreError: If check operation fails
        """
        try:
            metadata = self._metadata.get(archive_id)
            if not metadata:
                # Reload once in case metadata was updated by another instance.
                self._load_metadata()
                metadata = self._metadata.get(archive_id)
                if not metadata:
                    return False

            blob_name = metadata["blob_name"]
            blob_client = self.container_client.get_blob_client(blob_name)

            # Check if blob exists
            return blob_client.exists()

        except AzureError as e:
            raise ArchiveStoreError(
                f"Failed to check archive existence in Azure: {e}"
            ) from e
        except Exception as e:
            raise ArchiveStoreError(f"Failed to check archive existence: {e}") from e

    def delete_archive(self, archive_id: str) -> bool:
        """Delete archive from Azure Blob Storage.

        Args:
            archive_id: Unique archive identifier

        Returns:
            True if archive was deleted, False if not found

        Raises:
            ArchiveStoreError: If deletion operation fails
        """
        try:
            metadata = self._metadata.get(archive_id)
            if not metadata:
                return False

            blob_name = metadata["blob_name"]
            blob_client = self.container_client.get_blob_client(blob_name)

            # Delete blob (ignore if not found)
            try:
                blob_client.delete_blob()
                logger.info("Deleted archive blob %s", archive_id)
            except ResourceNotFoundError:
                logger.warning("Archive blob %s not found during deletion", archive_id)

            # Remove from metadata and hash index
            content_hash = self._metadata[archive_id].get("content_hash")
            del self._metadata[archive_id]
            if content_hash and content_hash in self._hash_index:
                del self._hash_index[content_hash]
            self._save_metadata()

            return True

        except AzureError as e:
            raise ArchiveStoreError(f"Failed to delete archive from Azure: {e}") from e
        except Exception as e:
            raise ArchiveStoreError(f"Failed to delete archive: {e}") from e

    def list_archives(self, source_name: str) -> list[dict[str, Any]]:
        """List all archives for a given source.

        Args:
            source_name: Name of the source

        Returns:
            List of archive metadata dictionaries

        Raises:
            ArchiveStoreError: If list operation fails
        """
        return [
            {
                "archive_id": metadata["archive_id"],
                "source_name": metadata["source_name"],
                "file_path": metadata["original_path"],
                "content_hash": metadata["content_hash"],
                "size_bytes": metadata["size_bytes"],
                "stored_at": metadata["stored_at"],
            }
            for metadata in self._metadata.values()
            if metadata.get("source_name") == source_name
        ]
