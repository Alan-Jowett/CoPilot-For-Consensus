# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for configurable source storage backends."""

from unittest.mock import patch

from app.service import IngestionService
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_Inmemory,
)
from copilot_config.generated.adapters.error_reporter import (
    AdapterConfig_ErrorReporter,
    DriverConfig_ErrorReporter_Silent,
)
from copilot_config.generated.adapters.logger import (
    AdapterConfig_Logger,
    DriverConfig_Logger_Silent,
)
from copilot_config.generated.adapters.message_bus import (
    AdapterConfig_MessageBus,
    DriverConfig_MessageBus_Noop,
)
from copilot_config.generated.adapters.metrics import (
    AdapterConfig_Metrics,
    DriverConfig_Metrics_Noop,
)
from copilot_error_reporting import create_error_reporter
from copilot_logging import create_logger
from copilot_message_bus import create_publisher
from copilot_metrics import create_metrics_collector
from copilot_storage import create_document_store

from .test_helpers import make_archive_store, make_config, make_source


def _make_noop_publisher():
    publisher = create_publisher(
        AdapterConfig_MessageBus(message_bus_type="noop", driver=DriverConfig_MessageBus_Noop()),
        enable_validation=False,
    )
    publisher.connect()
    return publisher


def _make_silent_logger(name: str = "test"):
    return create_logger(
        AdapterConfig_Logger(
            logger_type="silent",
            driver=DriverConfig_Logger_Silent(level="INFO", name=name),
        )
    )


def _make_noop_metrics():
    return create_metrics_collector(
        AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop())
    )


def _make_silent_error_reporter():
    return create_error_reporter(
        AdapterConfig_ErrorReporter(
            error_reporter_type="silent", driver=DriverConfig_ErrorReporter_Silent()
        )
    )


def _make_inmemory_store():
    store = create_document_store(
        AdapterConfig_DocumentStore(
            doc_store_type="inmemory", driver=DriverConfig_DocumentStore_Inmemory()
        ),
        enable_validation=False,
    )
    store.connect()
    return store


class TestSourceBackends:
    """Tests for source storage backend configuration."""

    def test_file_backend_uses_startup_sources(self, tmp_path):
        """Test that file backend uses sources from startup parameter."""
        # Create config with file backend
        config = make_config(storage_path=str(tmp_path / "storage"))
        config.service_settings.sources_store_type = "file"

        # Create sources to pass at startup
        startup_sources = [
            make_source(name="file-source-1", enabled=True),
            make_source(name="file-source-2", enabled=True),
            make_source(name="file-source-3", enabled=False),
        ]

        # Create service with file backend
        service = IngestionService(
            config,
            _make_noop_publisher(),
            sources=startup_sources,
            document_store=None,  # No document store for file backend
            logger=_make_silent_logger(),
            metrics=_make_noop_metrics(),
            error_reporter=_make_silent_error_reporter(),
            archive_store=make_archive_store(str(tmp_path / "storage")),
        )

        # Verify backend is file
        assert service._sources_store_type == "file"

        # Get enabled sources for ingestion
        enabled_sources = service._get_enabled_sources_for_ingestion()
        assert len(enabled_sources) == 2
        assert enabled_sources[0].name == "file-source-1"
        assert enabled_sources[1].name == "file-source-2"

        # Verify stats use startup sources
        stats = service.get_stats()
        assert stats["sources_configured"] == 3
        assert stats["sources_enabled"] == 2

    def test_document_store_backend_uses_document_store(self, tmp_path):
        """Test that document_store backend uses sources from document store."""
        # Create config with document_store backend (default)
        config = make_config(storage_path=str(tmp_path / "storage"))
        config.service_settings.sources_store_type = "document_store"

        # Create document store and add sources
        document_store = _make_inmemory_store()

        # Create service with empty startup sources (document store is source of truth)
        service = IngestionService(
            config,
            _make_noop_publisher(),
            sources=[],  # Empty startup sources
            document_store=document_store,
            logger=_make_silent_logger(),
            metrics=_make_noop_metrics(),
            error_reporter=_make_silent_error_reporter(),
            archive_store=make_archive_store(str(tmp_path / "storage")),
        )

        # Verify backend is document_store
        assert service._sources_store_type == "document_store"

        # Add sources via API
        service.create_source(make_source(name="db-source-1", enabled=True))
        service.create_source(make_source(name="db-source-2", enabled=True))
        service.create_source(make_source(name="db-source-3", enabled=False))

        # Get enabled sources for ingestion
        enabled_sources = service._get_enabled_sources_for_ingestion()
        assert len(enabled_sources) == 2
        assert enabled_sources[0].name == "db-source-1"
        assert enabled_sources[1].name == "db-source-2"

        # Verify stats use document store sources
        stats = service.get_stats()
        assert stats["sources_configured"] == 3
        assert stats["sources_enabled"] == 2

    def test_fallback_to_file_mode_when_no_document_store(self, tmp_path):
        """Test that service falls back to file mode when document_store is unavailable."""
        # Create config with document_store backend
        config = make_config(storage_path=str(tmp_path / "storage"))
        config.service_settings.sources_store_type = "document_store"

        startup_sources = [
            make_source(name="fallback-source-1", enabled=True),
        ]

        # Create service without document store
        service = IngestionService(
            config,
            _make_noop_publisher(),
            sources=startup_sources,
            document_store=None,  # No document store
            logger=_make_silent_logger(),
            metrics=_make_noop_metrics(),
            error_reporter=_make_silent_error_reporter(),
            archive_store=make_archive_store(str(tmp_path / "storage")),
        )

        # Should fall back to file mode
        assert service._sources_store_type == "file"

        # Should use startup sources
        enabled_sources = service._get_enabled_sources_for_ingestion()
        assert len(enabled_sources) == 1
        assert enabled_sources[0].name == "fallback-source-1"

    def test_scheduler_uses_configured_backend(self, tmp_path):
        """Test that ingest_all_enabled_sources uses the configured backend."""
        # Create config with document_store backend
        config = make_config(storage_path=str(tmp_path / "storage"))
        config.service_settings.sources_store_type = "document_store"

        document_store = _make_inmemory_store()

        service = IngestionService(
            config,
            _make_noop_publisher(),
            sources=[],
            document_store=document_store,
            logger=_make_silent_logger(),
            metrics=_make_noop_metrics(),
            error_reporter=_make_silent_error_reporter(),
            archive_store=make_archive_store(str(tmp_path / "storage")),
        )

        # Add a source via API
        service.create_source(make_source(name="api-source", enabled=True))

        # Mock ingest_archive to avoid actual ingestion
        with patch.object(service, "ingest_archive") as mock_ingest:
            results = service.ingest_all_enabled_sources()

            # Should have called ingest_archive for the API-created source
            assert len(results) == 1
            assert "api-source" in results
            assert results["api-source"] is None  # None means success
            assert mock_ingest.call_count == 1

    def test_startup_sources_merged_into_document_store(self, tmp_path):
        """Test that startup sources are merged into document store on initialization."""
        # Create config with document_store backend
        config = make_config(storage_path=str(tmp_path / "storage"))
        config.service_settings.sources_store_type = "document_store"

        document_store = _make_inmemory_store()

        startup_sources = [
            make_source(name="merged-source-1", enabled=True),
            make_source(name="merged-source-2", enabled=False),
        ]

        # Create service with startup sources
        service = IngestionService(
            config,
            _make_noop_publisher(),
            sources=startup_sources,
            document_store=document_store,
            logger=_make_silent_logger(),
            metrics=_make_noop_metrics(),
            error_reporter=_make_silent_error_reporter(),
            archive_store=make_archive_store(str(tmp_path / "storage")),
        )

        # Verify sources were merged into document store
        all_sources = service.list_sources()
        assert len(all_sources) == 2
        assert all_sources[0]["name"] == "merged-source-1"
        assert all_sources[1]["name"] == "merged-source-2"

        # Verify ingestion uses merged sources
        enabled_sources = service._get_enabled_sources_for_ingestion()
        assert len(enabled_sources) == 1
        assert enabled_sources[0].name == "merged-source-1"

    def test_duplicate_sources_not_merged_twice(self, tmp_path):
        """Test that duplicate startup sources are not created again in document store."""
        # Create config with document_store backend
        config = make_config(storage_path=str(tmp_path / "storage"))
        config.service_settings.sources_store_type = "document_store"

        document_store = _make_inmemory_store()

        # Pre-populate document store with a source
        document_store.insert_document("sources", make_source(name="existing-source"))

        startup_sources = [
            make_source(name="existing-source", enabled=True),  # Same as already in DB
            make_source(name="new-source", enabled=True),
        ]

        # Create service with startup sources
        service = IngestionService(
            config,
            _make_noop_publisher(),
            sources=startup_sources,
            document_store=document_store,
            logger=_make_silent_logger(),
            metrics=_make_noop_metrics(),
            error_reporter=_make_silent_error_reporter(),
            archive_store=make_archive_store(str(tmp_path / "storage")),
        )

        # Verify only 2 sources exist (no duplicate)
        all_sources = service.list_sources()
        assert len(all_sources) == 2
        source_names = {s["name"] for s in all_sources}
        assert source_names == {"existing-source", "new-source"}

    def test_invalid_sources_store_type_defaults_to_document_store(self, tmp_path):
        """Test that invalid sources_store_type value defaults to document_store with warning."""
        # Create config with invalid backend type
        config = make_config(storage_path=str(tmp_path / "storage"))
        config.service_settings.sources_store_type = "redis"  # Invalid value

        document_store = _make_inmemory_store()

        # Create service - should default to document_store backend despite invalid config
        service = IngestionService(
            config,
            _make_noop_publisher(),
            sources=[],
            document_store=document_store,
            logger=_make_silent_logger(),
            metrics=_make_noop_metrics(),
            error_reporter=_make_silent_error_reporter(),
            archive_store=make_archive_store(str(tmp_path / "storage")),
        )

        # Verify it defaulted to document_store mode
        assert service._sources_store_type == "document_store"

        # Verify it works as document_store backend
        service.create_source(make_source(name="test-source", enabled=True))
        sources = service.list_sources()
        assert len(sources) == 1
        assert sources[0]["name"] == "test-source"
