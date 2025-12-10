# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4

from copilot_events import EventPublisher, ArchiveIngestedEvent, ArchiveIngestionFailedEvent, ArchiveMetadata

from .config import IngestionConfig, SourceConfig
from .archive_fetcher import create_fetcher, calculate_file_hash

logger = logging.getLogger(__name__)


class IngestionService:
    """Main ingestion service for fetching and ingesting archives."""

    def __init__(
        self,
        config: IngestionConfig,
        publisher: EventPublisher,
        error_reporter: Optional[ErrorReporter] = None,
    ):
        """Initialize ingestion service.
        
        Args:
            config: Ingestion configuration
            publisher: Event publisher for publishing ingestion events
            error_reporter: Error reporter for structured error reporting (optional)
        """
        self.config = config
        self.publisher = publisher
        self.checksums: Dict[str, Dict[str, Any]] = {}
        
        # Initialize error reporter
        if error_reporter is None:
            self.error_reporter = create_error_reporter(
                reporter_type=config.error_reporter_type,
                dsn=config.sentry_dsn,
                environment=config.sentry_environment,
            )
        else:
            self.error_reporter = error_reporter
        
        self.load_checksums()

    def load_checksums(self) -> None:
        """Load checksums from metadata file."""
        checksums_path = os.path.join(self.config.storage_path, "metadata", "checksums.json")

        if os.path.exists(checksums_path):
            try:
                with open(checksums_path, "r") as f:
                    self.checksums = json.load(f)
                logger.info(f"Loaded {len(self.checksums)} checksums from {checksums_path}")
            except Exception as e:
                logger.warning(f"Failed to load checksums: {e}")
                self.error_reporter.report(
                    e,
                    context={
                        "operation": "load_checksums",
                        "checksums_path": checksums_path,
                    }
                )
                self.checksums = {}
        else:
            self.checksums = {}

    def save_checksums(self) -> None:
        """Save checksums to metadata file."""
        checksums_path = os.path.join(self.config.storage_path, "metadata", "checksums.json")

        try:
            os.makedirs(os.path.dirname(checksums_path), exist_ok=True)
            with open(checksums_path, "w") as f:
                json.dump(self.checksums, f, indent=2)
            logger.info(f"Saved {len(self.checksums)} checksums to {checksums_path}")
        except Exception as e:
            logger.error(f"Failed to save checksums: {e}")
            self.error_reporter.report(
                e,
                context={
                    "operation": "save_checksums",
                    "checksums_path": checksums_path,
                    "checksum_count": len(self.checksums),
                }
            )

    def is_file_already_ingested(self, file_hash: str) -> bool:
        """Check if a file has already been ingested.
        
        Args:
            file_hash: SHA256 hash of the file
            
        Returns:
            True if file has been ingested, False otherwise
        """
        return file_hash in self.checksums

    def add_checksum(
        self,
        file_hash: str,
        archive_id: str,
        file_path: str,
        first_seen: str,
    ) -> None:
        """Add a checksum entry.
        
        Args:
            file_hash: SHA256 hash of the file
            archive_id: Unique identifier for the archive
            file_path: Path where the archive is stored
            first_seen: ISO 8601 timestamp when first ingested
        """
        self.checksums[file_hash] = {
            "archive_id": archive_id,
            "file_path": file_path,
            "first_seen": first_seen,
        }

    def ingest_archive(
        self,
        source: SourceConfig,
        max_retries: Optional[int] = None,
    ) -> bool:
        """Ingest archives from a source.
        
        Args:
            source: Source configuration
            max_retries: Maximum number of retries (uses config default if None)
            
        Returns:
            True if ingestion succeeded, False otherwise
        """
        if max_retries is None:
            max_retries = self.config.retry_max_attempts

        ingestion_started_at = datetime.utcnow().isoformat() + "Z"

        retry_count = 0
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                logger.info(
                    f"Ingesting from source {source.name} (attempt {attempt + 1}/{max_retries + 1})"
                )

                # Create fetcher
                fetcher = create_fetcher(source)

                # Create output directory
                output_dir = os.path.join(self.config.storage_path, source.name)

                # Fetch archives
                success, file_paths, error_message = fetcher.fetch(output_dir)

                if not success:
                    last_error = error_message or "Unknown error"
                    retry_count += 1

                    if attempt < max_retries:
                        wait_time = self.config.retry_backoff_seconds * (2 ** attempt)
                        logger.warning(
                            f"Fetch attempt {attempt + 1} failed: {last_error}. "
                            f"Retrying in {wait_time} seconds..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        # All retries exhausted
                        self._publish_failure_event(
                            source,
                            last_error,
                            "FetchError",
                            retry_count,
                            ingestion_started_at,
                        )
                        return False

                # Process each file individually
                files_processed = 0
                files_skipped = 0

                for file_path in file_paths:
                    # Calculate hash for this file
                    file_hash = calculate_file_hash(file_path)
                    file_size = os.path.getsize(file_path)

                    # Check if already ingested
                    if self.is_file_already_ingested(file_hash):
                        logger.debug(
                            f"File {file_path} already ingested (hash: {file_hash[:16]}...)"
                        )
                        files_skipped += 1
                        continue

                    # Generate archive ID for this file
                    archive_id = str(uuid4())

                    # Create metadata
                    ingestion_completed_at = datetime.utcnow().isoformat() + "Z"

                    metadata = ArchiveMetadata(
                        archive_id=archive_id,
                        source_name=source.name,
                        source_type=source.source_type,
                        source_url=source.url,
                        file_path=file_path,
                        file_size_bytes=file_size,
                        file_hash_sha256=file_hash,
                        ingestion_started_at=ingestion_started_at,
                        ingestion_completed_at=ingestion_completed_at,
                        status="success",
                    )

                    # Store checksum
                    self.add_checksum(file_hash, archive_id, file_path, ingestion_started_at)

                    # Save metadata to log
                    self._save_ingestion_log(metadata)

                    # Publish success event
                    self._publish_success_event(metadata)

                    files_processed += 1

                # Save all checksums at once
                self.save_checksums()

                logger.info(
                    f"Successfully ingested from {source.name}: "
                    f"{files_processed} new files, {files_skipped} already ingested"
                )
                return True

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                retry_count += 1
                logger.error(f"Ingestion error: {last_error}")
                
                # Report error with context
                self.error_reporter.report(
                    e,
                    context={
                        "operation": "ingest_archive",
                        "source_name": source.name,
                        "source_type": source.source_type,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                    }
                )

                if attempt < max_retries:
                    wait_time = self.config.retry_backoff_seconds * (2 ** attempt)
                    logger.warning(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    # All retries exhausted
                    self._publish_failure_event(
                        source,
                        last_error,
                        "UnexpectedError",
                        retry_count,
                        ingestion_started_at,
                    )
                    return False

        return False

    def ingest_all_enabled_sources(self) -> Dict[str, bool]:
        """Ingest from all enabled sources.
        
        Returns:
            Dictionary mapping source name to ingestion success (True/False)
        """
        results = {}

        for source in self.config.get_enabled_sources():
            logger.info(f"Ingesting from source: {source.name}")
            success = self.ingest_archive(source)
            results[source.name] = success
            logger.info(f"Source {source.name}: {'success' if success else 'failed'}")

        return results

    def _calculate_directory_hash(self, dir_path: str) -> str:
        """Calculate hash of all files in a directory.
        
        Args:
            dir_path: Path to the directory
            
        Returns:
            Combined hash of all files
        """
        import hashlib

        combined_hash = hashlib.sha256()

        for root, dirs, files in os.walk(dir_path):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                file_hash = calculate_file_hash(file_path)
                combined_hash.update(file_hash.encode())

        return combined_hash.hexdigest()

    def _calculate_directory_size(self, dir_path: str) -> int:
        """Calculate total size of all files in a directory.
        
        Args:
            dir_path: Path to the directory
            
        Returns:
            Total size in bytes
        """
        total_size = 0

        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)

        return total_size

    def _save_ingestion_log(self, metadata: ArchiveMetadata) -> None:
        """Save ingestion metadata to log file.
        
        Args:
            metadata: Archive metadata to log
        """
        log_path = os.path.join(self.config.storage_path, "metadata", "ingestion_log.jsonl")

        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps(metadata.to_dict()) + "\n")
            logger.debug(f"Saved ingestion log entry to {log_path}")
        except Exception as e:
            logger.error(f"Failed to save ingestion log: {e}")
            self.error_reporter.report(
                e,
                context={
                    "operation": "save_ingestion_log",
                    "log_path": log_path,
                    "archive_id": metadata.archive_id,
                }
            )

    def _publish_success_event(self, metadata: ArchiveMetadata) -> None:
        """Publish ArchiveIngested event.
        
        Args:
            metadata: Archive metadata
        """
        event = ArchiveIngestedEvent(data=metadata.to_dict())

        success = self.publisher.publish(
            exchange="copilot.events",
            routing_key="archive.ingested",
            event=event.to_dict(),
        )

        if not success:
            logger.error(f"Failed to publish ArchiveIngested event for {metadata.archive_id}")
            self.error_reporter.capture_message(
                f"Failed to publish ArchiveIngested event",
                level="error",
                context={
                    "operation": "publish_success_event",
                    "archive_id": metadata.archive_id,
                    "source_name": metadata.source_name,
                }
            )

    def _publish_failure_event(
        self,
        source: SourceConfig,
        error_message: str,
        error_type: str,
        retry_count: int,
        ingestion_started_at: str,
    ) -> None:
        """Publish ArchiveIngestionFailed event.
        
        Args:
            source: Source configuration
            error_message: Error message
            error_type: Type of error
            retry_count: Number of retries attempted
            ingestion_started_at: When ingestion started
        """
        failed_at = datetime.utcnow().isoformat() + "Z"

        event = ArchiveIngestionFailedEvent(
            data={
                "source_name": source.name,
                "source_type": source.source_type,
                "source_url": source.url,
                "error_message": error_message,
                "error_type": error_type,
                "retry_count": retry_count,
                "ingestion_started_at": ingestion_started_at,
                "failed_at": failed_at,
            }
        )

        success = self.publisher.publish(
            exchange="copilot.events",
            routing_key="archive.ingestion.failed",
            event=event.to_dict(),
        )

        if not success:
            logger.error(f"Failed to publish ArchiveIngestionFailed event for {source.name}")
            self.error_reporter.capture_message(
                f"Failed to publish ArchiveIngestionFailed event",
                level="error",
                context={
                    "operation": "publish_failure_event",
                    "source_name": source.name,
                    "error_type": error_type,
                }
            )
