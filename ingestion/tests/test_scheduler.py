# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for ingestion scheduler."""

import time
from unittest.mock import patch

import pytest
from app.scheduler import IngestionScheduler
from app.service import IngestionService
from copilot_config.generated.adapters.document_store import AdapterConfig_DocumentStore, DriverConfig_DocumentStore_Inmemory
from copilot_config.generated.adapters.error_reporter import AdapterConfig_ErrorReporter, DriverConfig_ErrorReporter_Silent
from copilot_config.generated.adapters.logger import AdapterConfig_Logger, DriverConfig_Logger_Silent
from copilot_config.generated.adapters.message_bus import AdapterConfig_MessageBus, DriverConfig_MessageBus_Noop
from copilot_config.generated.adapters.metrics import AdapterConfig_Metrics, DriverConfig_Metrics_Noop
from copilot_error_reporting import create_error_reporter
from copilot_message_bus import create_publisher
from copilot_logging import create_logger
from copilot_metrics import create_metrics_collector
from copilot_storage import create_document_store

from .test_helpers import make_config, make_archive_store


@pytest.fixture
def service(tmp_path):
    """Create ingestion service for testing."""
    config = make_config(
        sources=[],
        storage_path=str(tmp_path / "raw_archives"),
    )

    publisher = create_publisher(
        AdapterConfig_MessageBus(message_bus_type="noop", driver=DriverConfig_MessageBus_Noop()),
        enable_validation=False,
    )
    publisher.connect()

    logger = create_logger(
        AdapterConfig_Logger(logger_type="silent", driver=DriverConfig_Logger_Silent(level="INFO", name="ingestion-test"))
    )

    metrics = create_metrics_collector(AdapterConfig_Metrics(metrics_type="noop", driver=DriverConfig_Metrics_Noop()))
    error_reporter = create_error_reporter(
        AdapterConfig_ErrorReporter(error_reporter_type="silent", driver=DriverConfig_ErrorReporter_Silent())
    )

    document_store = create_document_store(
        AdapterConfig_DocumentStore(doc_store_type="inmemory", driver=DriverConfig_DocumentStore_Inmemory()),
        enable_validation=False,
    )
    document_store.connect()

    archive_store = make_archive_store(base_path=config.storage_path)

    return IngestionService(
        config,
        publisher,
        document_store=document_store,
        logger=logger,
        metrics=metrics,
        error_reporter=error_reporter,
        archive_store=archive_store,
    )


class TestIngestionScheduler:
    """Tests for IngestionScheduler."""

    def test_scheduler_initialization(self, service):
        """Test scheduler initialization."""
        logger = create_logger(
            AdapterConfig_Logger(logger_type="silent", driver=DriverConfig_Logger_Silent(level="INFO", name="scheduler-test"))
        )
        scheduler = IngestionScheduler(
            service=service,
            interval_seconds=10,
            logger=logger,
        )

        assert scheduler.service == service
        assert scheduler.interval_seconds == 10
        assert scheduler.logger == logger
        assert not scheduler.is_running()

    def test_scheduler_start_stop(self, service):
        """Test starting and stopping the scheduler."""
        logger = create_logger(
            AdapterConfig_Logger(logger_type="silent", driver=DriverConfig_Logger_Silent(level="INFO", name="scheduler-test"))
        )
        scheduler = IngestionScheduler(
            service=service,
            interval_seconds=1,
            logger=logger,
        )

        # Start scheduler
        scheduler.start()
        assert scheduler.is_running()

        # Give it a moment to start
        time.sleep(0.1)

        # Stop scheduler
        scheduler.stop()
        assert not scheduler.is_running()

    def test_scheduler_runs_ingestion(self, service):
        """Test that scheduler calls service ingestion method."""
        logger = create_logger(
            AdapterConfig_Logger(logger_type="silent", driver=DriverConfig_Logger_Silent(level="INFO", name="scheduler-test"))
        )

        # Mock the ingestion method to avoid actual ingestion
        with patch.object(service, 'ingest_all_enabled_sources', return_value={}) as mock_ingest:
            scheduler = IngestionScheduler(
                service=service,
                interval_seconds=1,
                logger=logger,
            )

            # Start scheduler
            scheduler.start()

            # Wait for at least one ingestion run
            time.sleep(1.5)

            # Stop scheduler
            scheduler.stop()

            # Verify ingestion was called at least once
            assert mock_ingest.call_count >= 1

    def test_scheduler_handles_errors(self, service):
        """Test that scheduler continues after ingestion errors."""
        logger = create_logger(
            AdapterConfig_Logger(logger_type="silent", driver=DriverConfig_Logger_Silent(level="INFO", name="scheduler-test"))
        )

        # Mock the ingestion method to raise an error
        call_count = 0

        def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            return {}

        with patch.object(service, 'ingest_all_enabled_sources', side_effect=side_effect):
            scheduler = IngestionScheduler(
                service=service,
                interval_seconds=1,
                logger=logger,
            )

            # Start scheduler
            scheduler.start()

            # Wait for multiple runs
            time.sleep(2.5)

            # Stop scheduler
            scheduler.stop()

            # Verify scheduler continued after error
            assert call_count >= 2

    def test_scheduler_stop_when_not_running(self, service):
        """Test stopping scheduler when not running is safe."""
        logger = create_logger(
            AdapterConfig_Logger(logger_type="silent", driver=DriverConfig_Logger_Silent(level="INFO", name="scheduler-test"))
        )
        scheduler = IngestionScheduler(
            service=service,
            interval_seconds=10,
            logger=logger,
        )

        # Should not raise error
        scheduler.stop()
        assert not scheduler.is_running()

    def test_scheduler_start_when_already_running(self, service):
        """Test starting scheduler when already running is safe."""
        logger = create_logger(
            AdapterConfig_Logger(logger_type="silent", driver=DriverConfig_Logger_Silent(level="INFO", name="scheduler-test"))
        )
        scheduler = IngestionScheduler(
            service=service,
            interval_seconds=1,
            logger=logger,
        )

        # Start scheduler
        scheduler.start()
        assert scheduler.is_running()

        # Try to start again (should log warning but not error)
        scheduler.start()
        assert scheduler.is_running()

        # Clean up
        scheduler.stop()


