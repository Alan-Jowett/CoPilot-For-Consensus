# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Azure Blob Storage-based archive store implementation."""

import os
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import logging

from azure.storage.blob import BlobServiceClient, ContainerClient, BlobClient
from azure.core.exceptions import ResourceNotFoundError, AzureError

from .archive_store import (
    ArchiveStore,
    ArchiveStoreError,
    ArchiveStoreConnectionError,
    ArchiveNotFoundError,
)

logger = logging.getLogger(__name__)


class AzureBlobArchiveStore(ArchiveStore):
    """Azure Blob Storage-based archive storage.
    
    This implementation stores archives in Azure Blob Storage, enabling
    cloud-native deployments with scalability and high availability.
    
    Configuration is via environment variables:
    - AZURE_STORAGE_ACCOUNT: Storage account name
    - AZURE_STORAGE_KEY: Storage account key (primary or secondary)
    - AZURE_STORAGE_SAS_TOKEN: SAS token (alternative to key)
    - AZURE_STORAGE_CONTAINER: Container name for archives
    - AZURE_STORAGE_PREFIX: Optional path prefix for organizing blobs
    
    Metadata is stored as blob metadata and in a central JSON blob for
    efficient listing operations.
    """

    def __init__(
        self,
        account_name: str = None,
        account_key: str = None,
        sas_token: str = None,
        container_name: str = None,
        prefix: str = None,
        connection_string: str = None,
    ):
        """Initialize Azure Blob archive store.
        
        Args:
            account_name: Azure storage account name.
                         Defaults to AZURE_STORAGE_ACCOUNT env var
            account_key: Storage account key.
                        Defaults to AZURE_STORAGE_KEY env var
            sas_token: SAS token (alternative to account_key).
                      Defaults to AZURE_STORAGE_SAS_TOKEN env var
            container_name: Container name for archives.
                           Defaults to AZURE_STORAGE_CONTAINER env var or "archives"
            prefix: Optional path prefix for organizing blobs.
                   Defaults to AZURE_STORAGE_PREFIX env var or empty string
            connection_string: Full connection string (alternative to account_name/key).
                              Defaults to AZURE_STORAGE_CONNECTION_STRING env var
        """
        # Load configuration from environment if not provided
        self.account_name = account_name or os.getenv("AZURE_STORAGE_ACCOUNT")
        self.account_key = account_key or os.getenv("AZURE_STORAGE_KEY")
        self.sas_token = sas_token or os.getenv("AZURE_STORAGE_SAS_TOKEN")
        self.container_name = container_name or os.getenv(
            "AZURE_STORAGE_CONTAINER", "archives"
        )
        self.prefix = prefix or os.getenv("AZURE_STORAGE_PREFIX", "")
        self.connection_string = connection_string or os.getenv(
            "AZURE_STORAGE_CONNECTION_STRING"
        )

        # Ensure prefix ends with / if provided
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"

        # Validate configuration
        if not self.connection_string:
            if not self.account_name:
                raise ValueError(
                    "Azure Storage account name must be provided via "
                    "account_name parameter or AZURE_STORAGE_ACCOUNT env var"
                )
            if not self.account_key and not self.sas_token:
                raise ValueError(
                    "Azure Storage credentials must be provided via "
                    "account_key/AZURE_STORAGE_KEY or "
                    "sas_token/AZURE_STORAGE_SAS_TOKEN"
                )

        # Initialize Azure Blob Service Client
        try:
            if self.connection_string:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            elif self.sas_token:
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                self.blob_service_client = BlobServiceClient(
                    account_url=account_url, credential=self.sas_token
                )
            else:
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                self.blob_service_client = BlobServiceClient(
                    account_url=account_url, credential=self.account_key
                )

            # Get container client (create if not exists)
            self.container_client: ContainerClient = (
                self.blob_service_client.get_container_client(self.container_name)
            )
            
            # Create container if it doesn't exist
            try:
                self.container_client.create_container()
                logger.info(f"Created container: {self.container_name}")
            except Exception as e:
                # Container might already exist, which is fine
                if "ContainerAlreadyExists" not in str(e):
                    logger.debug(f"Container check: {e}")

        except Exception as e:
            raise ArchiveStoreConnectionError(
                f"Failed to connect to Azure Blob Storage: {e}"
            )

        # Metadata index blob name
        self.metadata_blob_name = f"{self.prefix}metadata/archives_index.json"
        
        # Load metadata index
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load metadata index from Azure Blob Storage."""
        try:
            blob_client = self.container_client.get_blob_client(self.metadata_blob_name)
            download_stream = blob_client.download_blob()
            metadata_json = download_stream.readall().decode("utf-8")
            self._metadata = json.loads(metadata_json)
            logger.debug(f"Loaded metadata index with {len(self._metadata)} entries")
        except ResourceNotFoundError:
            # Metadata blob doesn't exist yet (first run)
            self._metadata = {}
            logger.info("No existing metadata index found, starting fresh")
        except Exception as e:
            # Start with empty metadata if load fails
            self._metadata = {}
            logger.warning(f"Failed to load archive metadata: {e}")

    def _save_metadata(self) -> None:
        """Save metadata index to Azure Blob Storage."""
        try:
            metadata_json = json.dumps(self._metadata, indent=2)
            blob_client = self.container_client.get_blob_client(self.metadata_blob_name)
            blob_client.upload_blob(
                metadata_json.encode("utf-8"), overwrite=True
            )
            logger.debug(f"Saved metadata index with {len(self._metadata)} entries")
        except Exception as e:
            raise ArchiveStoreError(f"Failed to save metadata: {e}")

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
            
            # Update metadata index
            self._metadata[archive_id] = {
                "archive_id": archive_id,
                "source_name": source_name,
                "blob_name": blob_name,
                "original_path": file_path,
                "content_hash": content_hash,
                "size_bytes": len(content),
                "stored_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            self._save_metadata()
            
            logger.info(f"Stored archive {archive_id} for {source_name}")
            return archive_id
            
        except AzureError as e:
            raise ArchiveStoreError(f"Failed to store archive in Azure: {e}")
        except Exception as e:
            raise ArchiveStoreError(f"Failed to store archive: {e}")

    def get_archive(self, archive_id: str) -> Optional[bytes]:
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
                return None
            
            blob_name = metadata["blob_name"]
            blob_client = self.container_client.get_blob_client(blob_name)
            
            try:
                download_stream = blob_client.download_blob()
                content = download_stream.readall()
                logger.debug(f"Retrieved archive {archive_id}")
                return content
            except ResourceNotFoundError:
                # Metadata exists but blob is missing
                logger.warning(f"Archive {archive_id} metadata exists but blob not found")
                return None
                
        except AzureError as e:
            raise ArchiveStoreError(f"Failed to retrieve archive from Azure: {e}")
        except Exception as e:
            raise ArchiveStoreError(f"Failed to retrieve archive: {e}")

    def get_archive_by_hash(self, content_hash: str) -> Optional[str]:
        """Retrieve archive ID by content hash for deduplication.
        
        Args:
            content_hash: SHA256 hash of the archive content
            
        Returns:
            Archive ID if found, None otherwise
            
        Raises:
            ArchiveStoreError: If query operation fails
        """
        for archive_id, metadata in self._metadata.items():
            if metadata.get("content_hash") == content_hash:
                return archive_id
        return None

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
                return False
            
            blob_name = metadata["blob_name"]
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Check if blob exists
            return blob_client.exists()
            
        except AzureError as e:
            raise ArchiveStoreError(f"Failed to check archive existence in Azure: {e}")
        except Exception as e:
            raise ArchiveStoreError(f"Failed to check archive existence: {e}")

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
                logger.info(f"Deleted archive blob {archive_id}")
            except ResourceNotFoundError:
                logger.warning(f"Archive blob {archive_id} not found during deletion")
            
            # Remove from metadata
            del self._metadata[archive_id]
            self._save_metadata()
            
            return True
            
        except AzureError as e:
            raise ArchiveStoreError(f"Failed to delete archive from Azure: {e}")
        except Exception as e:
            raise ArchiveStoreError(f"Failed to delete archive: {e}")

    def list_archives(self, source_name: str) -> List[Dict[str, Any]]:
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
                "file_path": metadata["blob_name"],
                "content_hash": metadata["content_hash"],
                "size_bytes": metadata["size_bytes"],
                "stored_at": metadata["stored_at"],
            }
            for metadata in self._metadata.values()
            if metadata.get("source_name") == source_name
        ]
