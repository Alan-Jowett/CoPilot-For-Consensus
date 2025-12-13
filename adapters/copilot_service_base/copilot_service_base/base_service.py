# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Base service class with common functionality for all microservices."""

import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from copilot_events import EventPublisher, EventSubscriber
    from copilot_metrics import MetricsCollector
    from copilot_reporting import ErrorReporter

logger = logging.getLogger(__name__)


class BaseService(ABC):
    """Base class for all microservices with common patterns.
    
    Provides:
    - Stats tracking (processed count, failures, processing time)
    - Metrics collection integration
    - Error reporting integration
    - Common get_stats() implementation
    """
    
    def __init__(
        self,
        publisher: "EventPublisher",
        subscriber: "EventSubscriber",
        metrics_collector: Optional["MetricsCollector"] = None,
        error_reporter: Optional["ErrorReporter"] = None,
    ):
        """Initialize base service.
        
        Args:
            publisher: Event publisher for publishing events
            subscriber: Event subscriber for consuming events
            metrics_collector: Optional metrics collector
            error_reporter: Optional error reporter
        """
        self.publisher = publisher
        self.subscriber = subscriber
        self.metrics_collector = metrics_collector
        self.error_reporter = error_reporter
        
        # Common stats
        self._stats = {
            "processed_count": 0,
            "failure_count": 0,
            "last_processing_time": 0.0,
        }
    
    @abstractmethod
    def start(self):
        """Start the service and subscribe to events.
        
        Must be implemented by subclasses.
        """
        pass
    
    def increment_processed(self, count: int = 1):
        """Increment processed counter.
        
        Args:
            count: Number to increment by
        """
        self._stats["processed_count"] += count
    
    def increment_failures(self, count: int = 1):
        """Increment failure counter.
        
        Args:
            count: Number to increment by
        """
        self._stats["failure_count"] += count
    
    def set_processing_time(self, duration: float):
        """Set last processing time.
        
        Args:
            duration: Processing duration in seconds
        """
        self._stats["last_processing_time"] = duration
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.
        
        Returns:
            Dictionary of statistics
        """
        return self._stats.copy()
    
    def record_metric(
        self,
        metric_name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
        metric_type: str = "increment",
    ):
        """Record a metric if metrics collector is available.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            labels: Optional labels/tags for the metric
            metric_type: Type of metric ('increment', 'observe', 'histogram')
        """
        if not self.metrics_collector:
            return
        
        try:
            if metric_type == "increment":
                self.metrics_collector.increment(metric_name, value, labels=labels or {})
            elif metric_type == "observe":
                self.metrics_collector.observe(metric_name, value)
            elif metric_type == "histogram":
                self.metrics_collector.histogram(metric_name, value)
        except Exception as e:
            logger.warning(f"Failed to record metric {metric_name}: {e}")
    
    def report_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Report an error if error reporter is available.
        
        Args:
            error: Exception to report
            context: Optional context information
        """
        if self.error_reporter:
            try:
                self.error_reporter.report(error, context=context or {})
            except Exception as e:
                logger.warning(f"Failed to report error: {e}")
