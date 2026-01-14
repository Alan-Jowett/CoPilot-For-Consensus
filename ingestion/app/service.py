# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import hashlib
import json
import os
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from copilot_archive_fetcher import SourceConfig, calculate_file_hash, create_fetcher
from copilot_archive_store import ArchiveStore
from copilot_message_bus import ArchiveIngestedEvent, ArchiveIngestionFailedEvent, EventPublisher
from copilot_schema_validation import ArchiveMetadata
from copilot_logging import Logger, get_logger
from copilot_metrics import MetricsCollector, create_metrics_collector
from copilot_error_reporting import ErrorReporter, create_error_reporter
from copilot_storage import DocumentStore
from copilot_config import load_driver_config

from .exceptions import (
    FetchError,
    IngestionError,
    SourceConfigurationError,
)


def _expand(value: str | None) -> str | None:
    return os.path.expandvars(value) if isinstance(value, str) else value


def _source_from_mapping(source: dict[str, Any]) -> SourceConfig:
    """Convert a raw mapping into a fetcher SourceConfig.

    Args:
        source: Source configuration dictionary

    Returns:
        SourceConfig object

    Raises:
        SourceConfigurationError: If source is empty or missing required fields
    """
    try:
        expanded = dict(source)
        expanded["url"] = _expand(expanded.get("url"))
        expanded["username"] = _expand(expanded.get("username"))
        expanded["password"] = _expand(expanded.get("password"))
        return SourceConfig.from_mapping(expanded)
    except ValueError as e:
        raise SourceConfigurationError(str(e)) from e


def _sanitize_source_dict(source_dict: dict[str, Any]) -> dict[str, Any]:
    """Remove fields that should not be exposed or are not JSON serializable."""
    sanitized = source_dict.copy()
    sanitized.pop("_id", None)

    if "password" in sanitized and sanitized["password"]:
        sanitized["password"] = None

    return sanitized


def _enabled_sources(raw_sources: Iterable[Any]) -> list[SourceConfig]:
    """Normalize and filter enabled sources.

    Args:
        raw_sources: Iterable of raw source configurations

    Returns:
        List of enabled SourceConfig objects
    """
    logger = get_logger(__name__)
    enabled_sources: list[SourceConfig] = []

    for raw in raw_sources or []:
        try:
            if isinstance(raw, SourceConfig):
                source_cfg = raw
            elif isinstance(raw, dict):
                source_cfg = _source_from_mapping(raw)
            else:
                # Not supporting ad-hoc objects anymore; only dict/SourceConfig.
                raise SourceConfigurationError(f"Unsupported source object: {type(raw).__name__}")

            if source_cfg.enabled:
                enabled_sources.append(source_cfg)
        except SourceConfigurationError as e:
            logger.warning("Skipping invalid source configuration", error=str(e))
            continue

    return enabled_sources


class IngestionService:
    """Main ingestion service for fetching and ingesting archives."""

    def __init__(
        self,
        config: object,
        publisher: EventPublisher,
        document_store: DocumentStore | None = None,
        error_reporter: ErrorReporter | None = None,
        logger: Logger | None = None,
        metrics: MetricsCollector | None = None,
        archive_store: ArchiveStore | None = None,
    ):
        """Initialize ingestion service.

        Args:
            config: Ingestion configuration
            publisher: Event publisher for publishing ingestion events
            document_store: Document store for persisting archive metadata (optional)
            error_reporter: Error reporter for structured error reporting (optional)
            logger: Structured logger for observability (optional)
            metrics: Metrics collector for observability (optional)
            archive_store: Archive store for storing raw archives (optional, will be created if None)
        """
        self.config = config
        self.publisher = publisher
        self.document_store = document_store
        if logger is None:
            raise ValueError("logger is required and must be provided by the caller")
        self.logger = logger
        if metrics is None:
            metrics_config = load_driver_config(service=None, adapter="metrics", driver="noop", fields={})
            metrics = create_metrics_collector(driver_name="noop", driver_config=metrics_config)
        self.metrics = metrics

        # Get storage path from config or use default (store as instance variable for use throughout service)
        self.storage_path = config.storage_path
        self._ensure_storage_path(self.storage_path)

        # Initialize error reporter from adapter if not provided
        if error_reporter is None:
            try:
                error_reporter_adapter = config.get_adapter("error_reporter")
                if error_reporter_adapter is not None:
                    adapter_driver_config = getattr(error_reporter_adapter, "driver_config", None)
                    if adapter_driver_config is None:
                        fields: dict[str, Any] = {}
                    elif hasattr(adapter_driver_config, "config"):
                        fields = dict(getattr(adapter_driver_config, "config"))  # type: ignore[arg-type]
                    else:
                        fields = dict(adapter_driver_config)  # type: ignore[arg-type]

                    # Use load_driver_config to create proper DriverConfig
                    driver_config = load_driver_config(
                        service=None,
                        adapter="error_reporter",
                        driver=error_reporter_adapter.driver_name,
                        fields=fields,
                    )
                    self.error_reporter = create_error_reporter(
                        driver_name=error_reporter_adapter.driver_name,
                        driver_config=driver_config,
                    )
                else:
                    # No error_reporter adapter in config, use silent with empty config
                    silent_config = load_driver_config(service=None, adapter="error_reporter", driver="silent", fields={})
                    self.error_reporter = create_error_reporter(driver_name="silent", driver_config=silent_config)
            except Exception:
                # Exception during error_reporter creation, fallback to silent
                silent_config = load_driver_config(service=None, adapter="error_reporter", driver="silent", fields={})
                self.error_reporter = create_error_reporter(driver_name="silent", driver_config=silent_config)
        else:
            self.error_reporter = error_reporter

        if archive_store is None:
            raise ValueError("archive_store is required and must be provided by the caller")
        self.archive_store = archive_store
        # Capture backend type once from schema-driven config; fallback to store driver when present
        self.archive_store_type = getattr(config, "archive_store_type", None) or getattr(
            archive_store, "driver_name", archive_store.__class__.__name__
        )

        # Source status tracking
        self._source_status: dict[str, dict[str, Any]] = {}
        self._stats = {
            "total_files_ingested": 0,
            "last_ingestion_at": None,
        }

        # Initialize archive metadata cache for performance optimization
        self._archive_metadata_cache: dict[str, dict[str, dict[str, Any]]] = {}

        # Sources cache for dynamic source management from document store
        self._sources_cache: list[dict[str, Any]] | None = None

    @staticmethod
    def _ensure_storage_path(storage_path: str) -> None:
        storage_dir = Path(storage_path)
        storage_dir.mkdir(parents=True, exist_ok=True)
        (storage_dir / "metadata").mkdir(exist_ok=True)

    def delete_archives_for_source(self, source_name: str) -> int:
        """Delete all archives associated with a source from document store.

        This allows re-ingestion of previously processed files from the source.

        Args:
            source_name: Name of the source

        Returns:
            Number of archives deleted
        """
        deleted_count = 0

        if self.document_store:
            try:
                # Query all archives for this source
                archives = self.document_store.query_documents(
                    "archives",
                    {"source": source_name}
                )

                # Delete each archive
                for archive in archives:
                    archive_id = archive.get("_id") or archive.get("id")
                    if archive_id:
                        try:
                            self.document_store.delete_document("archives", str(archive_id))
                            deleted_count += 1
                        except Exception as e:
                            self.logger.warning(
                                "Failed to delete archive from document store",
                                archive_id=archive_id,
                                error=str(e),
                            )

                if deleted_count > 0:
                    self.logger.info(
                        "Deleted archives for source from document store",
                        source_name=source_name,
                        count=deleted_count,
                    )
            except Exception as e:
                self.logger.error(
                    "Failed to delete archives for source",
                    source_name=source_name,
                    error=str(e),
                    exc_info=True,
                )

        return deleted_count

    def ingest_archive(
        self,
        source: object,
        max_retries: int | None = None,
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
            max_retries = self.config.max_retries

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
                output_dir = os.path.join(self.storage_path, source.name)

                # Fetch archives
                success, file_paths, error_message = fetcher.fetch(output_dir)

                if not success:
                    last_error = error_message or "Unknown error"
                    retry_count += 1

                    if attempt < max_retries:
                        wait_time = self.config.request_timeout_seconds * (2 ** attempt)
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
                    # Read file content once
                    with open(file_path, "rb") as f:
                        file_content = f.read()

                    # Calculate hash from content (avoids re-reading file)
                    file_hash = hashlib.sha256(file_content).hexdigest()
                    file_size = len(file_content)

                    # Check if already ingested using document store
                    if self._is_archive_already_stored(file_hash):
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

                    # Store archive via ArchiveStore
                    try:
                        archive_id = self.archive_store.store_archive(
                            source_name=source.name,
                            file_path=file_path,
                            content=file_content,
                        )
                        self.logger.info(
                            "Stored archive via ArchiveStore",
                            archive_id=archive_id,
                            source_name=source.name,
                            file_path=file_path,
                            file_size=file_size,
                        )
                    except Exception as e:
                        self.logger.error(
                            "Failed to store archive via ArchiveStore",
                            error=str(e),
                            file_path=file_path,
                            source_name=source.name,
                            exc_info=True,
                        )
                        self.error_reporter.report(
                            e,
                            context={
                                "operation": "store_archive",
                                "file_path": file_path,
                                "source_name": source.name,
                            }
                        )
                        # Skip this file and continue with others
                        continue

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

                    # Save metadata to log
                    self._save_ingestion_log(metadata)

                    # Write to archives collection in document store
                    self._write_archive_record(
                        archive_id,
                        source,
                        file_hash,
                        ingestion_completed_at,
                    )

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
                    wait_time = self.config.request_timeout_seconds * (2 ** attempt)
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

    def ingest_all_enabled_sources(self) -> dict[str, Exception | None]:
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
        log_path = os.path.join(self.storage_path, "metadata", "ingestion_log.jsonl")

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

    def _is_archive_already_stored(self, file_hash: str) -> bool:
        """Check if an archive with the given hash is already stored.

        Uses the document store to check for existing archives with the same SHA-256 hash.
        This replaces the local checksums.json cache.

        Args:
            file_hash: SHA256 hash of the file

        Returns:
            True if archive with this hash exists in document store, False otherwise
        """
        if self.document_store is None:
            return False

        try:
            # Query document store for archives with this hash
            existing_archives = self.document_store.query_documents(
                "archives",
                {"file_hash": file_hash},
                limit=1
            )
            return len(existing_archives) > 0
        except Exception as e:
            # If query fails, log warning but allow processing to continue
            # This ensures ingestion doesn't fail due to temporary document store issues
            # However, we report the error prominently via metrics and error reporting
            self.logger.warning(
                "Failed to check if archive already stored - processing may result in duplicates",
                error=str(e),
                file_hash=file_hash,
                exc_info=True,
            )

            # Increment metric for document store query failures to make silent failures visible
            if self.metrics:
                self.metrics.increment("ingestion_deduplication_check_failed_total")

            if self.error_reporter:
                self.error_reporter.report(
                    e,
                    context={
                        "operation": "check_archive_already_stored",
                        "collection": "archives",
                        "file_hash": file_hash,
                    },
                )
            return False

    def _write_archive_record(
        self,
        archive_id: str,
        source: SourceConfig,
        file_hash: str,
        ingestion_date: str,
    ) -> None:
        """Write archive record to document store.

        Creates a document in the archives collection with metadata about the
        ingested archive. The status is set to 'pending' initially, and will
        be updated to 'processed' by the parsing service after parsing completes.

        Args:
            archive_id: Unique identifier for the archive
            source: Source configuration
            file_hash: SHA-256 hash of the archive content
            storage_backend: ArchiveStore backend type (local, mongodb, azure_blob)
            ingestion_date: ISO 8601 timestamp when ingestion completed
        """
        if self.document_store is None:
            self.logger.debug(
                "Document store not configured; skipping archive record write",
                archive_id=archive_id,
            )
            return

        try:
            # Get archive metadata from ArchiveStore
            archive_metadata = None
            if self.archive_store:
                # Use per-source in-memory cache (initialized in __init__) to avoid repeated
                # list_archives calls when processing multiple archives for a source.
                archive_lookup = self._archive_metadata_cache.get(source.name)
                if archive_lookup is None:
                    archives = self.archive_store.list_archives(source.name)
                    archive_lookup = {
                        archive.get("archive_id"): archive
                        for archive in archives
                        if archive.get("archive_id") is not None
                    }
                    self._archive_metadata_cache[source.name] = archive_lookup

                archive_metadata = archive_lookup.get(archive_id)
                
                # If metadata not found in cache, refresh the cache in case new archives
                # were just stored by store_archive() and not yet in the cache
                if not archive_metadata:
                    # Reload list_archives to get newly stored archives
                    archives = self.archive_store.list_archives(source.name)
                    archive_lookup = {
                        archive.get("archive_id"): archive
                        for archive in archives
                        if archive.get("archive_id") is not None
                    }
                    self._archive_metadata_cache[source.name] = archive_lookup
                    archive_metadata = archive_lookup.get(archive_id)

            # Determine archive format from stored metadata or default to mbox
            archive_format = "mbox"
            file_size_bytes = 0
            if archive_metadata:
                file_path = archive_metadata.get("original_path", "")
                file_ext = os.path.splitext(file_path)[1].lstrip('.')
                archive_format = file_ext if file_ext else "mbox"
                file_size_bytes = archive_metadata.get("size_bytes", 0)
            elif self.archive_store and not archive_metadata:
                # ArchiveStore is configured but no metadata was found for this archive,
                # even after cache refresh. This indicates a critical inconsistency: the
                # archive was just stored via store_archive() but cannot be found in the
                # backend's metadata. Log error but do not abort: create an archive document
                # with minimal metadata. Parsing can still proceed using the ArchiveIngested
                # event data and archive_id, but metadata and status tracking in the archives
                # collection may be incomplete.
                self.logger.error(
                    "Archive metadata not found in ArchiveStore after storing and refreshing cache; "
                    "creating archive document with minimal metadata",
                    archive_id=archive_id,
                    source=source.name,
                    storage_backend=self.archive_store_type,
                )
                # Proceed with default values to avoid blocking the pipeline

            archive_doc = {
                "_id": archive_id,  # Canonical identifier
                "file_hash": file_hash,
                "file_size_bytes": file_size_bytes,
                "source": source.name,
                "source_type": source.source_type,
                "source_url": source.url,
                "format": archive_format,
                "ingestion_date": ingestion_date,
                "message_count": 0,  # Will be updated by parsing service
                "storage_backend": self.archive_store_type,  # Track which backend is storing this
                "status": "pending",  # Will be updated to 'processed' or 'failed' by parsing
                "created_at": ingestion_date,
            }

            self.document_store.insert_document("archives", archive_doc)
            self.logger.info(
                "Wrote archive record to document store",
                archive_id=archive_id,
                source=source.name,
                storage_backend=self.archive_store_type,
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
                        "storage_backend": self.archive_store_type,
                    }
                )

    def _publish_success_event(self, metadata: ArchiveMetadata) -> None:
        """Publish ArchiveIngested event.

        Args:
            metadata: Archive metadata

        Raises:
            Exception: Re-raises any exception from publisher to ensure visibility
        """
        # Convert metadata to dict and remove storage-specific fields
        event_data = metadata.to_dict()
        event_data.pop('status', None)  # Remove status field if present
        event_data.pop('file_path', None)  # Remove file_path (storage-specific, not for events)

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
        tags: dict[str, str],
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

    def _record_failure_metrics(self, tags: dict[str, str], started_monotonic: float) -> None:
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
    def _metric_tags(source: SourceConfig) -> dict[str, str]:
        """Build consistent metric tags for a source."""
        name = getattr(source, "name", None) or (source.get("name") if isinstance(source, dict) else None)
        src_type = (
            getattr(source, "source_type", None)
            or (source.get("source_type") if isinstance(source, dict) else None)
        )
        return {
            "source_name": name or "unknown",
            "source_type": src_type or "unknown",
        }

    # Source management API methods

    def get_stats(self) -> dict[str, Any]:
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

    def list_sources(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """List all sources.

        Args:
            enabled_only: If True, only return enabled sources

        Returns:
            List of source configurations
        """
        # Try to load from document store cache first
        if self._sources_cache is None:
            self._reload_sources()

        sources = self._sources_cache or []

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

    def get_source(self, source_name: str) -> dict[str, Any] | None:
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

    def create_source(self, source_data: dict[str, Any]) -> dict[str, Any]:
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

    def _get_source_doc_id(self, source_name: str) -> str | None:
        """Get the document ID for a source by name.

        Args:
            source_name: Name of the source

        Returns:
            Document ID as string, or None if source not found

        Raises:
            ValueError: If source document exists but has no id field
        """
        docs = self.document_store.query_documents("sources", {"name": source_name}, limit=1)
        if not docs:
            return None

        doc = docs[0]
        # Try "id" first (Cosmos DB), then "_id" (MongoDB/InMemory).
        # Use explicit None checks so falsy but valid IDs (e.g., 0, "") are preserved.
        doc_id = doc.get("id")
        if doc_id is None:
            doc_id = doc.get("_id")

        if doc_id is None:
            raise ValueError(f"Source document for '{source_name}' has no id field")

        return str(doc_id)

    def update_source(self, source_name: str, source_data: dict[str, Any]) -> dict[str, Any] | None:
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

        try:
            # Get the document ID
            doc_id = self._get_source_doc_id(source_name)
            if doc_id is None:
                return None

            # Update in document store using the document ID
            self.document_store.update_document(
                "sources",
                doc_id,
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
        except ValueError:
            # Re-raise ValueError directly (includes missing id field errors)
            raise
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

        try:
            # Get the document ID
            doc_id = self._get_source_doc_id(source_name)
            if doc_id is None:
                return False

            # Delete from document store using the document ID
            self.document_store.delete_document("sources", doc_id)

            # Reload sources from config
            self._reload_sources()

            # Clear status tracking
            if source_name in self._source_status:
                del self._source_status[source_name]

            self.logger.info("Source deleted", source_name=source_name)

            return True
        except ValueError:
            # Re-raise ValueError directly (includes missing id field errors)
            raise
        except Exception as e:
            self.logger.error("Failed to delete source", error=str(e), exc_info=True)
            raise ValueError(f"Failed to delete source: {str(e)}")

    def trigger_ingestion(self, source_name: str) -> tuple[bool, str]:
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
            # Delete existing archives to force re-ingestion
            deleted_count = self.delete_archives_for_source(source_name)
            if deleted_count > 0:
                self.logger.info(
                    "Trigger ingestion: deleted archives to force re-ingestion",
                    source_name=source_name,
                    archives_deleted=deleted_count,
                )

            # Convert to SourceConfig
            source_cfg = _source_from_mapping(source)

            # Run ingestion
            self.ingest_archive(source_cfg)

            return True, f"Ingestion triggered successfully for '{source_name}'"
        except Exception as e:
            return False, f"Ingestion failed: {str(e)}"

    def get_source_status(self, source_name: str) -> dict[str, Any] | None:
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
        """Reload sources from document store after CRUD operations.

        Sources are stored separately in the document store as a dynamic configuration,
        independent of the static service config loaded at startup. This method is called
        after create_source(), update_source(), and delete_source() operations to refresh
        the in-memory sources cache.
        """
        if not self.document_store:
            self._sources_cache = []
            return

        try:
            # Query all sources from the document store
            sources = self.document_store.query_documents("sources", {})
            self._sources_cache = sources or []
            self.logger.debug(
                "Reloaded sources from document store",
                sources_count=len(self._sources_cache)
            )
        except Exception as e:
            self.logger.warning(
                "Failed to reload sources from document store",
                error=str(e),
                exc_info=True
            )
            self._sources_cache = []

    def _update_source_status(
        self,
        source_name: str,
        status: str,
        error: str | None = None,
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

