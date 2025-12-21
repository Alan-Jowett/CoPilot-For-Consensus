# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Iterable, List, Tuple

from copilot_events import EventPublisher, ArchiveIngestedEvent, ArchiveIngestionFailedEvent, ArchiveMetadata
from copilot_logging import Logger, create_logger
from copilot_metrics import MetricsCollector, create_metrics_collector
from copilot_reporting import ErrorReporter, create_error_reporter
from copilot_archive_fetcher import create_fetcher, calculate_file_hash, SourceConfig
from copilot_storage import DocumentStore

from .exceptions import (
    IngestionError,
    SourceConfigurationError,
    FetchError,
)

DEFAULT_CONFIG = {
    "storage_path": "/data/raw_archives",
    "message_bus_host": "messagebus",
    "message_bus_port": 5672,
    "message_bus_user": "guest",
    "message_bus_password": "guest",
    "message_bus_type": "rabbitmq",
    "ingestion_schedule_cron": "0 */6 * * *",
    "blob_storage_enabled": False,
    "blob_storage_connection_string": None,
    "blob_storage_container": "raw-archives",
    "log_level": "INFO",
    "log_type": "stdout",
    "logger_name": "ingestion-service",
    "metrics_backend": "noop",
    "retry_max_attempts": 3,
    "retry_backoff_seconds": 60,
    "error_reporter_type": "console",
    "sentry_dsn": None,
    "sentry_environment": "production",
    "doc_store_type": "mongodb",
    "doc_store_host": "documentdb",
    "doc_store_port": 27017,
    "doc_store_name": "copilot",
    "doc_store_user": "root",
    "doc_store_password": "example",
    "sources": [],
}


class _ConfigWithDefaults:
    """Wrapper that combines a loaded config with defaults, without modifying the original."""
    
    def __init__(self, config: object):
        # Store base config and allow per-instance overrides without mutating base
        self._config = config
        self._overrides: Dict[str, Any] = {}

    def __setattr__(self, name: str, value: Any) -> None:
        """Allow overrides while keeping base config immutable."""
        if name in {"_config", "_overrides"}:
            object.__setattr__(self, name, value)
            return
        # Record overrides instead of mutating the base config
        overrides = object.__getattribute__(self, "_overrides")
        overrides[name] = value
    
    def __getattr__(self, name: str) -> Any:
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        # Try to get from loaded config first
        if hasattr(self._config, name):
            return getattr(self._config, name)
        # Fall back to defaults
        if name in DEFAULT_CONFIG:
            return DEFAULT_CONFIG[name]
        # Raise AttributeError if not found
        raise AttributeError(f"Configuration key '{name}' not found")


def _apply_defaults(config: object) -> object:
    """Ensure all expected config fields exist with defaults, without modifying the original config."""
    return _ConfigWithDefaults(config)


def _expand(value: Optional[str]) -> Optional[str]:
    return os.path.expandvars(value) if isinstance(value, str) else value


def _source_from_mapping(source: Dict[str, Any]) -> SourceConfig:
    """Convert a raw mapping into a fetcher SourceConfig.
    
    Args:
        source: Source configuration dictionary
        
    Returns:
        SourceConfig object
        
    Raises:
        SourceConfigurationError: If source is empty or missing required fields
    """
    if not source:
        raise SourceConfigurationError("Source configuration is empty")
    required = {"name", "source_type", "url"}
    if not required.issubset(source):
        missing = required - set(source.keys())
        raise SourceConfigurationError(
            f"Source configuration missing required fields: {missing}"
        )

    return SourceConfig(
        name=source["name"],
        source_type=source["source_type"],
        url=_expand(source.get("url")),
        port=source.get("port"),
        username=_expand(source.get("username")),
        password=_expand(source.get("password")),
        folder=source.get("folder"),
    )


def _sanitize_source_dict(source_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Remove fields that should not be exposed or are not JSON serializable."""
    sanitized = source_dict.copy()
    sanitized.pop("_id", None)

    if "password" in sanitized and sanitized["password"]:
        sanitized["password"] = None

    return sanitized


def _enabled_sources(raw_sources: Iterable[Any]) -> List[SourceConfig]:
    """Normalize and filter enabled sources.
    
    Args:
        raw_sources: Iterable of raw source configurations
        
    Returns:
        List of enabled SourceConfig objects
    """
    enabled_sources: List[SourceConfig] = []

    for raw in raw_sources or []:
        try:
            enabled = True
            if isinstance(raw, dict):
                enabled = raw.get("enabled", True)
                source_cfg = _source_from_mapping(raw)
            elif isinstance(raw, SourceConfig):
                enabled = getattr(raw, "enabled", True)
                source_cfg = SourceConfig(
                    name=raw.name,
                    source_type=raw.source_type,
                    url=_expand(raw.url),
                    port=getattr(raw, "port", None),
                    username=_expand(getattr(raw, "username", None)),
                    password=_expand(getattr(raw, "password", None)),
                    folder=getattr(raw, "folder", None),
                )
            else:
                enabled = getattr(raw, "enabled", True)
                source_cfg = SourceConfig(
                    name=getattr(raw, "name", None),
                    source_type=getattr(raw, "source_type", None),
                    url=_expand(getattr(raw, "url", None)),
                    port=getattr(raw, "port", None),
                    username=_expand(getattr(raw, "username", None)),
                    password=_expand(getattr(raw, "password", None)),
                    folder=getattr(raw, "folder", None),
                )

            if enabled:
                enabled_sources.append(source_cfg)
        except SourceConfigurationError as e:
            # Log but skip invalid source configurations
            # This allows the service to continue with valid sources
            logger = logging.getLogger(__name__)
            logger.warning(f"Skipping invalid source configuration: {e}")
            continue

    return enabled_sources


class IngestionService:
    """Main ingestion service for fetching and ingesting archives."""

    def __init__(
        self,
        config: object,
        publisher: EventPublisher,
        document_store: Optional[DocumentStore] = None,
        error_reporter: Optional[ErrorReporter] = None,
        logger: Optional[Logger] = None,
        metrics: Optional[MetricsCollector] = None,
    ):
        """Initialize ingestion service.
        
        Args:
            config: Ingestion configuration
            publisher: Event publisher for publishing ingestion events
            document_store: Document store for persisting archive metadata (optional)
            error_reporter: Error reporter for structured error reporting (optional)
            logger: Structured logger for observability (optional)
            metrics: Metrics collector for observability (optional)
        """
        self.config = _apply_defaults(config)
        self.publisher = publisher
        self.document_store = document_store
        self.checksums: Dict[str, Dict[str, Any]] = {}
        self.logger = logger or create_logger(
            logger_type=config.log_type,
            level=config.log_level,
            name=config.logger_name,
        )
        self.metrics = metrics or create_metrics_collector(backend=config.metrics_backend)
        self._ensure_storage_path(self.config.storage_path)
        self._initial_storage_path = self.config.storage_path
        
        # Initialize error reporter
        if error_reporter is None:
            self.error_reporter = create_error_reporter(
                reporter_type=config.error_reporter_type,
                dsn=config.sentry_dsn,
                environment=config.sentry_environment,
                logger_name=config.logger_name,
            )
        else:
            self.error_reporter = error_reporter
        
        # Source status tracking
        self._source_status: Dict[str, Dict[str, Any]] = {}
        self._stats = {
            "total_files_ingested": 0,
            "last_ingestion_at": None,
        }
        
        self.load_checksums()

    @staticmethod
    def _ensure_storage_path(storage_path: str) -> None:
        storage_dir = Path(storage_path)
        storage_dir.mkdir(parents=True, exist_ok=True)
        (storage_dir / "metadata").mkdir(exist_ok=True)

    def load_checksums(self) -> None:
        """Load checksums from metadata file.
        
        If loading fails, starts with empty checksums to allow service to continue.
        This is intentional recovery - the service can start even if checksums
        can't be loaded (though files may be reprocessed).
        """
        checksums_path = os.path.join(self.config.storage_path, "metadata", "checksums.json")

        if os.path.exists(checksums_path):
            try:
                with open(checksums_path, "r") as f:
                    self.checksums = json.load(f)
                self.logger.info(
                    "Loaded checksums",
                    checksum_count=len(self.checksums),
                    checksums_path=checksums_path,
                )
            except Exception as e:
                self.logger.warning("Failed to load checksums", error=str(e), exc_info=True)
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
        """Save checksums to metadata file.
        
        Raises on failure to ensure caller is aware that checksums weren't persisted.
        """
        checksums_path = os.path.join(self.config.storage_path, "metadata", "checksums.json")
        try:
            if self.config.storage_path != self._initial_storage_path:
                raise ValueError("Storage path changed after initialization")
            if not os.path.exists(self.config.storage_path):
                raise FileNotFoundError(f"Storage path does not exist: {self.config.storage_path}")
            os.makedirs(os.path.dirname(checksums_path), exist_ok=True)
            with open(checksums_path, "w") as f:
                json.dump(self.checksums, f, indent=2)
            self.logger.info(
                "Saved checksums",
                checksum_count=len(self.checksums),
                checksums_path=checksums_path,
            )
        except Exception as e:
            self.logger.error("Failed to save checksums", error=str(e), exc_info=True)
            self.error_reporter.report(
                e,
                context={
                    "operation": "save_checksums",
                    "checksums_path": checksums_path,
                    "checksum_count": len(self.checksums),
                }
            )
            raise

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

    def delete_checksums_for_source(self, source_name: str) -> int:
        """Delete all checksums associated with a source.
        
        This allows re-ingestion of previously processed files from the source.
        
        Args:
            source_name: Name of the source
            
        Returns:
            Number of checksums deleted
        """
        # Find all checksums that have file paths belonging to this source
        # Files from a source are stored in: {storage_path}/{source_name}/*
        # Add trailing separator to ensure exact directory matching
        source_path_prefix = os.path.join(self.config.storage_path, source_name) + os.sep
        
        hashes_to_delete = []
        for file_hash, metadata in self.checksums.items():
            file_path = metadata.get("file_path", "")
            # Check if this file belongs to the source
            if file_path.startswith(source_path_prefix):
                hashes_to_delete.append(file_hash)
        
        # Delete the identified hashes
        for file_hash in hashes_to_delete:
            del self.checksums[file_hash]
        
        if hashes_to_delete:
            self.logger.info(
                "Deleted checksums for source",
                source_name=source_name,
                count=len(hashes_to_delete),
            )
        
        return len(hashes_to_delete)

    def ingest_archive(
        self,
        source: object,
        max_retries: Optional[int] = None,
    ) -> None:
        """Ingest archives from a source.
        
        Args:
            source: Source configuration
            max_retries: Maximum number of retries (uses config default if None)
            
        Raises:
            SourceConfigurationError: If source configuration is invalid
            FetchError: If fetching archives fails after all retries
            ChecksumPersistenceError: If saving checksums fails
            ArchivePublishError: If publishing archive events fails
        """
        # Normalize source into fetcher SourceConfig
        try:
            if isinstance(source, dict):
                source = _source_from_mapping(source)
            elif not isinstance(source, SourceConfig):
                source = _source_from_mapping(getattr(source, "__dict__", {}))
        except SourceConfigurationError:
            # Re-raise configuration errors directly
            raise

        if max_retries is None:
            max_retries = self.config.retry_max_attempts

        ingestion_started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        started_monotonic = time.monotonic()
        metric_tags = self._metric_tags(source)

        retry_count = 0
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                self.logger.info(
                    "Ingesting from source",
                    source_name=source.name,
                    source_type=source.source_type,
                    attempt=attempt + 1,
                    max_attempts=max_retries + 1,
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
                        self.logger.warning(
                            "Fetch attempt failed",
                            source_name=source.name,
                            attempt=attempt + 1,
                            wait_time_seconds=wait_time,
                            error=last_error,
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        # All retries exhausted - raise exception
                        try:
                            self._publish_failure_event(
                                source,
                                last_error,
                                "FetchError",
                                retry_count,
                                ingestion_started_at,
                            )
                        except Exception as publish_error:
                            # Event publishing failed but fetch definitely failed too
                            # Log both errors to ensure visibility
                            self.logger.error(
                                "Failed to publish ingestion failure event",
                                source_name=source.name,
                                original_error=last_error,
                                publish_error=str(publish_error),
                            )
                            # Wrap both errors in FetchError
                            raise FetchError(
                                f"Fetch failed: {last_error}. Event publish also failed: {publish_error}",
                                source_name=source.name,
                                retry_count=retry_count
                            )
                        self._record_failure_metrics(metric_tags, started_monotonic)
                        # Update source status tracking
                        self._update_source_status(
                            source.name,
                            status="failed",
                            error=last_error,
                        )
                        raise FetchError(
                            last_error,
                            source_name=source.name,
                            retry_count=retry_count
                        )

                # Process each file individually
                files_processed = 0
                files_skipped = 0

                for file_path in file_paths:
                    # Calculate hash for this file
                    file_hash = calculate_file_hash(file_path)
                    file_size = os.path.getsize(file_path)

                    # Check if already ingested
                    if self.is_file_already_ingested(file_hash):
                        self.logger.debug(
                            "File already ingested",
                            file_path=file_path,
                            file_hash=file_hash,
                            source_name=source.name,
                        )
                        files_skipped += 1
                        self.metrics.increment(
                            "ingestion_files_total",
                            tags={**metric_tags, "status": "skipped"},
                        )
                        continue

                    # Generate deterministic archive ID from file hash (first 16 chars)
                    # This ensures same file always produces same archive_id for idempotent ingestion
                    archive_id = file_hash[:16]

                    # Create metadata
                    ingestion_completed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

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

                    # Write to archives collection in document store
                    self._write_archive_record(archive_id, source, file_path, ingestion_completed_at)

                    # Publish success event
                    self._publish_success_event(metadata)

                    self.metrics.increment(
                        "ingestion_files_total",
                        tags={**metric_tags, "status": "success"},
                    )
                    self.metrics.increment(
                        "ingestion_documents_total",
                        tags={**metric_tags, "status": "success"},
                    )
                    self.metrics.observe(
                        "ingestion_file_size_bytes",
                        file_size,
                        tags=metric_tags,
                    )

                    files_processed += 1

                # Save all checksums at once
                self.save_checksums()

                duration_seconds = time.monotonic() - started_monotonic
                self.logger.info(
                    "Ingestion completed",
                    source_name=source.name,
                    files_processed=files_processed,
                    files_skipped=files_skipped,
                    duration_seconds=duration_seconds,
                )
                self._record_success_metrics(
                    metric_tags,
                    duration_seconds,
                    files_processed,
                    files_skipped,
                )
                
                # Update source status tracking
                self._update_source_status(
                    source.name,
                    status="success",
                    files_processed=files_processed,
                    files_skipped=files_skipped,
                )
                
                # Success - method returns normally without exception
                return

            except (FetchError, SourceConfigurationError):
                # Don't retry configuration or already-handled fetch errors
                raise
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                retry_count += 1
                self.logger.error(
                    "Ingestion error",
                    error=last_error,
                    attempt=attempt + 1,
                    source_name=source.name,
                )
                
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
                    self.logger.warning(
                        "Retrying after error",
                        wait_time_seconds=wait_time,
                        attempt=attempt + 1,
                        source_name=source.name,
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    # All retries exhausted - raise IngestionError
                    try:
                        self._publish_failure_event(
                            source,
                            last_error,
                            "UnexpectedError",
                            retry_count,
                            ingestion_started_at,
                        )
                    except Exception as publish_error:
                        # Event publishing failed but ingestion definitely failed too
                        # Log both errors to ensure visibility
                        self.logger.error(
                            "Failed to publish ingestion failure event",
                            source_name=source.name,
                            original_error=last_error,
                            publish_error=str(publish_error),
                        )
                        # Wrap both errors in IngestionError
                        self._record_failure_metrics(metric_tags, started_monotonic)
                        raise IngestionError(
                            f"Ingestion failed: {last_error}. Event publish also failed: {publish_error}"
                        ) from e
                    self._record_failure_metrics(metric_tags, started_monotonic)
                    # Update source status tracking
                    self._update_source_status(
                        source.name,
                        status="failed",
                        error=last_error,
                    )
                    raise IngestionError(last_error) from e

        # Should never reach here due to loop structure, but add safety
        raise IngestionError(f"Ingestion failed for unknown reason (source: {source.name})")

    def ingest_all_enabled_sources(self) -> Dict[str, Optional[Exception]]:
        """Ingest from all enabled sources.
        
        Attempts ingestion for each enabled source, catching exceptions to allow
        other sources to be processed even if one fails.
        
        Returns:
            Dictionary mapping source name to exception (None if successful).
            - None value indicates success
            - Exception object indicates failure with details
        """
        results = {}

        for source in _enabled_sources(getattr(self.config, "sources", [])):
            self.logger.info("Starting source ingestion", source_name=source.name)
            try:
                self.ingest_archive(source)
                results[source.name] = None  # Success
                self.logger.info(
                    "Source ingestion finished",
                    source_name=source.name,
                    status="success",
                )
            except Exception as e:
                results[source.name] = e  # Store exception
                self.logger.error(
                    "Source ingestion failed",
                    source_name=source.name,
                    status="failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )

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
        
        This is best-effort audit logging. Failures are logged but not raised
        since audit log failures should not block ingestion processing.
        
        Args:
            metadata: Archive metadata to log
        """
        log_path = os.path.join(self.config.storage_path, "metadata", "ingestion_log.jsonl")

        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps(metadata.to_dict()) + "\n")
            self.logger.debug(
                "Saved ingestion log entry",
                log_path=log_path,
                archive_id=metadata.archive_id,
            )
        except Exception as e:
            self.logger.error("Failed to save ingestion log", error=str(e), exc_info=True)
            self.error_reporter.report(
                e,
                context={
                    "operation": "save_ingestion_log",
                    "log_path": log_path,
                    "archive_id": metadata.archive_id,
                }
            )

    def _write_archive_record(
        self,
        archive_id: str,
        source: SourceConfig,
        file_path: str,
        ingestion_date: str,
    ) -> None:
        """Write archive record to document store.
        
        Creates a document in the archives collection with metadata about the
        ingested archive. The status is set to 'pending' initially, and will
        be updated to 'processed' by the parsing service after parsing completes.
        
        Args:
            archive_id: Unique identifier for the archive
            source: Source configuration
            file_path: Path where the archive is stored
            ingestion_date: ISO 8601 timestamp when ingestion completed
        """
        if self.document_store is None:
            self.logger.debug(
                "Document store not configured; skipping archive record write",
                archive_id=archive_id,
            )
            return

        try:
            # Determine archive format from file extension
            file_ext = os.path.splitext(file_path)[1].lstrip('.')
            archive_format = file_ext if file_ext else "mbox"  # default to mbox

            # Compute required fields for schema validation
            file_hash = calculate_file_hash(file_path)
            file_size_bytes = os.path.getsize(file_path)

            archive_doc = {
                "_id": archive_id,  # Canonical identifier
                "file_hash": file_hash,
                "file_size_bytes": file_size_bytes,
                "source": source.name,
                "source_url": source.url,
                "format": archive_format,
                "ingestion_date": ingestion_date,
                "message_count": 0,  # Will be updated by parsing service
                "file_path": file_path,
                "status": "pending",  # Will be updated to 'processed' or 'failed' by parsing
                "created_at": ingestion_date,
            }

            self.document_store.insert_document("archives", archive_doc)
            self.logger.info(
                "Wrote archive record to document store",
                archive_id=archive_id,
                source=source.name,
                file_path=file_path,
            )
            
            # Emit metric for archive creation with pending status
            if self.metrics:
                self.metrics.increment(
                    "ingestion_archive_status_transitions_total",
                    tags={"status": "pending", "collection": "archives"}
                )
        except Exception as e:
            # Log but don't raise - archive record write is not critical to ingestion
            # The parsing service can still process based on the event
            self.logger.warning(
                "Failed to write archive record to document store",
                error=str(e),
                archive_id=archive_id,
                source=source.name,
                exc_info=True,
            )
            if self.error_reporter:
                self.error_reporter.report(
                    e,
                    context={
                        "operation": "write_archive_record",
                        "archive_id": archive_id,
                        "source": source.name,
                        "file_path": file_path,
                    }
                )

    def _publish_success_event(self, metadata: ArchiveMetadata) -> None:
        """Publish ArchiveIngested event.
        
        Args:
            metadata: Archive metadata
            
        Raises:
            Exception: Re-raises any exception from publisher to ensure visibility
        """
        # Convert metadata to dict and remove status field (not part of event schema)
        event_data = metadata.to_dict()
        event_data.pop('status', None)  # Remove status field if present
        
        try:
            event = ArchiveIngestedEvent(data=event_data)

            self.publisher.publish(
                exchange="copilot.events",
                routing_key="archive.ingested",
                event=event.to_dict(),
            )
        except Exception as e:
            self.logger.error(
                "Failed to publish success event",
                archive_id=metadata.archive_id,
                source_name=metadata.source_name,
                error=str(e),
            )
            self.error_reporter.report(
                e,
                context={
                    "operation": "publish_success_event",
                    "archive_id": metadata.archive_id,
                    "source_name": metadata.source_name,
                }
            )
            raise  # Re-raise to ensure operator visibility

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
            
        Raises:
            Exception: Re-raises any exception from publisher to ensure visibility
        """
        failed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        try:
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

            self.publisher.publish(
                exchange="copilot.events",
                routing_key="archive.ingestion.failed",
                event=event.to_dict(),
            )
        except Exception as e:
            self.logger.error(
                "Failed to publish failure event",
                source_name=source.name,
                error_type=error_type,
                error=str(e),
            )
            self.error_reporter.report(
                e,
                context={
                    "operation": "publish_failure_event",
                    "source_name": source.name,
                    "error_type": error_type,
                }
            )
            raise  # Re-raise to ensure operator visibility

    def _record_success_metrics(
        self,
        tags: Dict[str, str],
        duration_seconds: float,
        files_processed: int,
        files_skipped: int,
    ) -> None:
        """Emit success metrics for a source ingestion."""
        self.metrics.increment(
            "ingestion_sources_total",
            tags={**tags, "status": "success"},
        )
        self.metrics.observe(
            "ingestion_duration_seconds",
            duration_seconds,
            tags=tags,
        )
        self.metrics.gauge(
            "ingestion_files_processed",
            float(files_processed),
            tags=tags,
        )
        self.metrics.gauge(
            "ingestion_files_skipped",
            float(files_skipped),
            tags=tags,
        )

    def _record_failure_metrics(self, tags: Dict[str, str], started_monotonic: float) -> None:
        """Emit failure metrics for a source ingestion."""
        duration_seconds = time.monotonic() - started_monotonic
        self.metrics.increment(
            "ingestion_sources_total",
            tags={**tags, "status": "failure"},
        )
        self.metrics.observe(
            "ingestion_duration_seconds",
            duration_seconds,
            tags=tags,
        )

    @staticmethod
    def _metric_tags(source: SourceConfig) -> Dict[str, str]:
        """Build consistent metric tags for a source."""
        name = getattr(source, "name", None) or (source.get("name") if isinstance(source, dict) else None)
        src_type = getattr(source, "source_type", None) or (source.get("source_type") if isinstance(source, dict) else None)
        return {
            "source_name": name or "unknown",
            "source_type": src_type or "unknown",
        }
    
    # Source management API methods
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.
        
        Returns:
            Dictionary with service statistics
        """
        sources = _enabled_sources(getattr(self.config, "sources", []))
        
        return {
            "sources_configured": len(getattr(self.config, "sources", [])),
            "sources_enabled": len(sources),
            "total_files_ingested": self._stats.get("total_files_ingested", 0),
            "last_ingestion_at": self._stats.get("last_ingestion_at"),
            "version": getattr(self, "version", "unknown"),
        }
    
    def list_sources(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all sources.
        
        Args:
            enabled_only: If True, only return enabled sources
            
        Returns:
            List of source configurations
        """
        sources = getattr(self.config, "sources", [])
        
        result = []
        for source in sources:
            if isinstance(source, dict):
                source_dict = _sanitize_source_dict(source)
            else:
                source_dict = {
                    "name": getattr(source, "name", None),
                    "source_type": getattr(source, "source_type", None),
                    "url": getattr(source, "url", None),
                    "port": getattr(source, "port", None),
                    "username": getattr(source, "username", None),
                    # Do not expose passwords; represent as None when present
                    "password": None,
                    "folder": getattr(source, "folder", None),
                    "enabled": getattr(source, "enabled", True),
                    "schedule": getattr(source, "schedule", None),
                }
            
            # Ensure password is not exposed
            if "password" in source_dict and source_dict["password"]:
                source_dict["password"] = None
            
            if enabled_only and not source_dict.get("enabled", True):
                continue
            
            result.append(source_dict)
        
        return result
    
    def get_source(self, source_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific source by name.
        
        Args:
            source_name: Name of the source
            
        Returns:
            Source configuration or None if not found
        """
        sources = self.list_sources()
        for source in sources:
            if source.get("name") == source_name:
                return source
        return None
    
    def create_source(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new source.
        
        Args:
            source_data: Source configuration data
            
        Returns:
            Created source configuration
            
        Raises:
            ValueError: If source name already exists or data is invalid
        """
        if not self.document_store:
            raise ValueError("Document store not configured")
        
        # Validate required fields
        required_fields = {"name", "source_type", "url"}
        if not required_fields.issubset(source_data.keys()):
            missing = required_fields - set(source_data.keys())
            raise ValueError(f"Missing required fields: {missing}")
        
        # Check if source already exists
        existing = self.get_source(source_data["name"])
        if existing:
            raise ValueError(f"Source '{source_data['name']}' already exists")
        
        # Add default enabled flag if not present
        if "enabled" not in source_data:
            source_data["enabled"] = True
        
        # Store in document store
        try:
            self.document_store.insert_document("sources", source_data)
            
            # Reload sources from config
            self._reload_sources()
            
            self.logger.info("Source created", source_name=source_data["name"])
            
            # Return created source (without exposing password)
            return _sanitize_source_dict(source_data)
        except Exception as e:
            self.logger.error("Failed to create source", error=str(e), exc_info=True)
            raise ValueError(f"Failed to create source: {str(e)}")
    
    def update_source(self, source_name: str, source_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing source.
        
        Args:
            source_name: Name of the source to update
            source_data: Updated source configuration
            
        Returns:
            Updated source configuration or None if not found
            
        Raises:
            ValueError: If update fails
        """
        if not self.document_store:
            raise ValueError("Document store not configured")
        
        # Check if source exists
        existing = self.get_source(source_name)
        if not existing:
            return None
        
        try:
            # Update in document store
            self.document_store.update_document(
                "sources",
                {"name": source_name},
                source_data
            )
            
            # Reload sources from config
            self._reload_sources()
            
            self.logger.info("Source updated", source_name=source_name)
            
            # Return updated source (without exposing password)
            updated = source_data.copy()
            if "password" in updated and updated["password"]:
                updated["password"] = None
            
            return updated
        except Exception as e:
            self.logger.error("Failed to update source", error=str(e), exc_info=True)
            raise ValueError(f"Failed to update source: {str(e)}")
    
    def delete_source(self, source_name: str) -> bool:
        """Delete a source.
        
        Args:
            source_name: Name of the source to delete
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            ValueError: If deletion fails
        """
        if not self.document_store:
            raise ValueError("Document store not configured")
        
        # Check if source exists
        existing = self.get_source(source_name)
        if not existing:
            return False
        
        try:
            # Delete from document store
            self.document_store.delete_document("sources", {"name": source_name})
            
            # Reload sources from config
            self._reload_sources()
            
            # Clear status tracking
            if source_name in self._source_status:
                del self._source_status[source_name]
            
            self.logger.info("Source deleted", source_name=source_name)
            
            return True
        except Exception as e:
            self.logger.error("Failed to delete source", error=str(e), exc_info=True)
            raise ValueError(f"Failed to delete source: {str(e)}")
    
    def trigger_ingestion(self, source_name: str) -> Tuple[bool, str]:
        """Trigger manual ingestion for a source.
        
        When explicitly triggered, this method deletes any existing checksums
        for the source to force re-ingestion of all files, even if they were
        previously processed.
        
        Args:
            source_name: Name of the source to ingest
            
        Returns:
            Tuple of (success, message)
        """
        # Find the source
        source = self.get_source(source_name)
        if not source:
            return False, f"Source '{source_name}' not found"
        
        if not source.get("enabled", True):
            return False, f"Source '{source_name}' is disabled"
        
        try:
            # Delete existing checksums to force re-ingestion
            deleted_count = self.delete_checksums_for_source(source_name)
            if deleted_count > 0:
                self.logger.info(
                    "Trigger ingestion: deleted checksums to force re-ingestion",
                    source_name=source_name,
                    checksums_deleted=deleted_count,
                )
                # Save checksums after deletion to persist the change immediately
                self.save_checksums()
            
            # Convert to SourceConfig
            source_cfg = _source_from_mapping(source)
            
            # Run ingestion
            # Note: ingest_archive will save checksums again after adding new ones
            self.ingest_archive(source_cfg)
            
            return True, f"Ingestion triggered successfully for '{source_name}'"
        except Exception as e:
            return False, f"Ingestion failed: {str(e)}"
    
    def get_source_status(self, source_name: str) -> Optional[Dict[str, Any]]:
        """Get status information for a source.
        
        Args:
            source_name: Name of the source
            
        Returns:
            Status information or None if source not found
        """
        source = self.get_source(source_name)
        if not source:
            return None
        
        # Get status from tracking or create default
        status = self._source_status.get(source_name, {})
        
        return {
            "name": source_name,
            "enabled": source.get("enabled", True),
            "last_run_at": status.get("last_run_at"),
            "last_run_status": status.get("last_run_status"),
            "last_error": status.get("last_error"),
            "next_run_at": status.get("next_run_at"),
            "files_processed": status.get("files_processed", 0),
            "files_skipped": status.get("files_skipped", 0),
        }
    
    def _reload_sources(self):
        """Reload sources from document store."""
        if not self.document_store:
            return
        
        try:
            from copilot_config.providers import DocStoreConfigProvider
            
            doc_store_provider = DocStoreConfigProvider(self.document_store)
            sources = doc_store_provider.query_documents_from_collection("sources") or []
            
            # Update config sources - handle both _ConfigWithDefaults and SimpleNamespace
            if hasattr(self.config, "_overrides"):
                self.config._overrides["sources"] = sources
            else:
                # For SimpleNamespace, just update the attribute
                self.config.sources = sources
            
            self.logger.info("Sources reloaded", source_count=len(sources))
        except Exception as e:
            self.logger.warning("Failed to reload sources", error=str(e), exc_info=True)
    
    def _update_source_status(
        self,
        source_name: str,
        status: str,
        error: Optional[str] = None,
        files_processed: int = 0,
        files_skipped: int = 0,
    ):
        """Update status tracking for a source.
        
        Args:
            source_name: Name of the source
            status: Status (success, failed)
            error: Error message if failed
            files_processed: Number of files processed
            files_skipped: Number of files skipped
        """
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        if source_name not in self._source_status:
            self._source_status[source_name] = {}
        
        self._source_status[source_name].update({
            "last_run_at": now,
            "last_run_status": status,
            "last_error": error,
            "files_processed": files_processed,
            "files_skipped": files_skipped,
        })
        
        # Update global stats
        if status == "success":
            self._stats["total_files_ingested"] += files_processed
            self._stats["last_ingestion_at"] = now

