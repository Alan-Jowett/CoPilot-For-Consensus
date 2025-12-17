# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Iterable, List

from copilot_events import EventPublisher, ArchiveIngestedEvent, ArchiveIngestionFailedEvent, ArchiveMetadata
from copilot_logging import Logger, create_logger
from copilot_metrics import MetricsCollector, create_metrics_collector
from copilot_reporting import ErrorReporter, create_error_reporter
from copilot_archive_fetcher import create_fetcher, calculate_file_hash, SourceConfig
from copilot_storage import DocumentStore

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


def _source_from_mapping(source: Dict[str, Any]) -> Optional[SourceConfig]:
    """Convert a raw mapping into a fetcher SourceConfig."""
    if not source:
        return None
    required = {"name", "source_type", "url"}
    if not required.issubset(source):
        return None

    return SourceConfig(
        name=source["name"],
        source_type=source["source_type"],
        url=_expand(source.get("url")),
        port=source.get("port"),
        username=_expand(source.get("username")),
        password=_expand(source.get("password")),
        folder=source.get("folder"),
    )


def _enabled_sources(raw_sources: Iterable[Any]) -> List[SourceConfig]:
    """Normalize and filter enabled sources."""
    enabled_sources: List[SourceConfig] = []

    for raw in raw_sources or []:
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

        if enabled and source_cfg is not None:
            enabled_sources.append(source_cfg)

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

    def ingest_archive(
        self,
        source: object,
        max_retries: Optional[int] = None,
    ) -> bool:
        """Ingest archives from a source.
        
        Args:
            source: Source configuration
            max_retries: Maximum number of retries (uses config default if None)
            
        Returns:
            True if ingestion succeeded, False otherwise
        """
        # Normalize source into fetcher SourceConfig
        if isinstance(source, dict):
            source = _source_from_mapping(source)
        elif not isinstance(source, SourceConfig):
            source = _source_from_mapping(getattr(source, "__dict__", {}))

        if source is None:
            return False

        if max_retries is None:
            max_retries = self.config.retry_max_attempts

        ingestion_started_at = datetime.utcnow().isoformat() + "Z"
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
                        # All retries exhausted
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
                            # Don't re-raise - we still want to return False to indicate failure
                        self._record_failure_metrics(metric_tags, started_monotonic)
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
                return True

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
                    # All retries exhausted
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
                        # Don't re-raise - we still want to return False to indicate failure
                    self._record_failure_metrics(metric_tags, started_monotonic)
                    return False

        return False

    def ingest_all_enabled_sources(self) -> Dict[str, bool]:
        """Ingest from all enabled sources.
        
        Returns:
            Dictionary mapping source name to ingestion success (True/False)
        """
        results = {}

        for source in _enabled_sources(getattr(self.config, "sources", [])):
            self.logger.info("Starting source ingestion", source_name=source.name)
            success = self.ingest_archive(source)
            results[source.name] = success
            self.logger.info(
                "Source ingestion finished",
                source_name=source.name,
                status="success" if success else "failed",
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

            archive_doc = {
                "archive_id": archive_id,
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
        failed_at = datetime.utcnow().isoformat() + "Z"

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
