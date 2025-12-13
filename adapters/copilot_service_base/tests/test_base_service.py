# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for base service class."""

import pytest
from unittest.mock import Mock

from copilot_service_base.base_service import BaseService


class ConcreteService(BaseService):
    """Concrete implementation of BaseService for testing."""
    
    def start(self):
        """Implementation of abstract method."""
        pass


class TestBaseService:
    """Tests for BaseService class."""
    
    def test_initialization(self):
        """Test that base service initializes correctly."""
        publisher = Mock()
        subscriber = Mock()
        metrics = Mock()
        reporter = Mock()
        
        service = ConcreteService(
            publisher=publisher,
            subscriber=subscriber,
            metrics_collector=metrics,
            error_reporter=reporter,
        )
        
        assert service.publisher is publisher
        assert service.subscriber is subscriber
        assert service.metrics_collector is metrics
        assert service.error_reporter is reporter
    
    def test_stats_initialization(self):
        """Test that stats are initialized to zero."""
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
        )
        
        stats = service.get_stats()
        assert stats["processed_count"] == 0
        assert stats["failure_count"] == 0
        assert stats["last_processing_time"] == 0.0
    
    def test_increment_processed(self):
        """Test incrementing processed counter."""
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
        )
        
        service.increment_processed(5)
        assert service.get_stats()["processed_count"] == 5
        
        service.increment_processed()
        assert service.get_stats()["processed_count"] == 6
    
    def test_increment_failures(self):
        """Test incrementing failure counter."""
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
        )
        
        service.increment_failures(3)
        assert service.get_stats()["failure_count"] == 3
        
        service.increment_failures()
        assert service.get_stats()["failure_count"] == 4
    
    def test_set_processing_time(self):
        """Test setting processing time."""
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
        )
        
        service.set_processing_time(12.5)
        assert service.get_stats()["last_processing_time"] == 12.5
    
    def test_get_stats_returns_copy(self):
        """Test that get_stats returns a copy, not reference."""
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
        )
        
        stats1 = service.get_stats()
        stats1["processed_count"] = 999
        
        stats2 = service.get_stats()
        assert stats2["processed_count"] == 0
    
    def test_record_metric_increment(self):
        """Test recording increment metric."""
        metrics = Mock()
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
            metrics_collector=metrics,
        )
        
        service.record_metric(
            "test_counter",
            value=5,
            labels={"status": "success"},
            metric_type="increment"
        )
        
        metrics.increment.assert_called_once_with(
            "test_counter",
            5,
            labels={"status": "success"}
        )
    
    def test_record_metric_observe(self):
        """Test recording observe metric."""
        metrics = Mock()
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
            metrics_collector=metrics,
        )
        
        service.record_metric(
            "test_gauge",
            value=10.5,
            metric_type="observe"
        )
        
        metrics.observe.assert_called_once_with("test_gauge", 10.5)
    
    def test_record_metric_histogram(self):
        """Test recording histogram metric."""
        metrics = Mock()
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
            metrics_collector=metrics,
        )
        
        service.record_metric(
            "test_histogram",
            value=3.14,
            metric_type="histogram"
        )
        
        metrics.histogram.assert_called_once_with("test_histogram", 3.14)
    
    def test_record_metric_without_collector(self):
        """Test that recording metrics without collector doesn't raise."""
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
        )
        
        # Should not raise
        service.record_metric("test_metric", metric_type="increment")
    
    def test_record_metric_handles_errors(self):
        """Test that metric recording errors are handled gracefully."""
        metrics = Mock()
        metrics.increment.side_effect = Exception("metric error")
        
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
            metrics_collector=metrics,
        )
        
        # Should not raise
        service.record_metric("test_metric", metric_type="increment")
    
    def test_report_error(self):
        """Test error reporting."""
        reporter = Mock()
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
            error_reporter=reporter,
        )
        
        error = ValueError("test error")
        context = {"key": "value"}
        
        service.report_error(error, context)
        
        reporter.report.assert_called_once_with(error, context=context)
    
    def test_report_error_without_reporter(self):
        """Test that error reporting without reporter doesn't raise."""
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
        )
        
        # Should not raise
        service.report_error(ValueError("test"))
    
    def test_report_error_handles_errors(self):
        """Test that error reporting errors are handled gracefully."""
        reporter = Mock()
        reporter.report.side_effect = Exception("reporter error")
        
        service = ConcreteService(
            publisher=Mock(),
            subscriber=Mock(),
            error_reporter=reporter,
        )
        
        # Should not raise
        service.report_error(ValueError("test"))
