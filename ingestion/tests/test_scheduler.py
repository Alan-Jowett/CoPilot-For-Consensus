# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for ingestion scheduler."""

import time
import pytest
from unittest.mock import Mock, patch

from copilot_events import NoopPublisher
from copilot_storage import InMemoryDocumentStore
from copilot_logging import create_logger
from copilot_metrics import NoOpMetricsCollector

from app.service import IngestionService
from app.scheduler import IngestionScheduler
from .test_helpers import make_config


@pytest.fixture
def service(tmp_path):
    """Create ingestion service for testing."""
    config = make_config(
        sources=[],
        storage_path=str(tmp_path / "raw_archives"),
    )
    
    publisher = NoopPublisher()
    publisher.connect()
    
    logger = create_logger(logger_type="silent", level="INFO", name="ingestion-test")
    metrics = NoOpMetricsCollector()
    
    document_store = InMemoryDocumentStore()
    document_store.connect()
    
    return IngestionService(
        config,
        publisher,
        document_store=document_store,
        logger=logger,
        metrics=metrics,
    )


class TestIngestionScheduler:
    """Tests for IngestionScheduler."""
    
    def test_scheduler_initialization(self, service):
        """Test scheduler initialization."""
        logger = create_logger(logger_type="silent", level="INFO", name="scheduler-test")
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
        logger = create_logger(logger_type="silent", level="INFO", name="scheduler-test")
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
        logger = create_logger(logger_type="silent", level="INFO", name="scheduler-test")
        
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
        logger = create_logger(logger_type="silent", level="INFO", name="scheduler-test")
        
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
        logger = create_logger(logger_type="silent", level="INFO", name="scheduler-test")
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
        logger = create_logger(logger_type="silent", level="INFO", name="scheduler-test")
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
