# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Scheduler for periodic ingestion tasks."""

import threading
import time
from typing import Any

from copilot_logging import Logger


class IngestionScheduler:
    """Scheduler for periodic ingestion from enabled sources."""

    def __init__(
        self,
        service: Any,
        interval_seconds: int = 21600,  # Default: 6 hours
        logger: Logger | None = None,
    ):
        """Initialize the scheduler.

        Args:
            service: IngestionService instance
            interval_seconds: Interval between ingestion runs in seconds
            logger: Logger instance
        """
        self.service = service
        self.interval_seconds = interval_seconds
        self.logger = logger
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self):
        """Start the scheduler in a background thread."""
        if self._running:
            if self.logger:
                self.logger.warning("Scheduler already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._running = True

        if self.logger:
            self.logger.info(
                "Ingestion scheduler started",
                interval_seconds=self.interval_seconds,
            )

    def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return

        if self.logger:
            self.logger.info("Stopping ingestion scheduler")

        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

        self._running = False

        if self.logger:
            self.logger.info("Ingestion scheduler stopped")

    def _run_loop(self):
        """Main scheduler loop."""
        while not self._stop_event.is_set():
            try:
                if self.logger:
                    self.logger.info("Starting scheduled ingestion run")

                start_time = time.monotonic()
                results = self.service.ingest_all_enabled_sources()
                duration = time.monotonic() - start_time

                # Count successes and failures
                successful = sum(1 for exc in results.values() if exc is None)
                failed = len(results) - successful

                if self.logger:
                    self.logger.info(
                        "Scheduled ingestion run completed",
                        duration_seconds=duration,
                        total_sources=len(results),
                        successful=successful,
                        failed=failed,
                    )

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        "Error in scheduled ingestion run",
                        error=str(e),
                        exc_info=True,
                    )

            # Wait for next interval or stop signal
            self._stop_event.wait(self.interval_seconds)

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running
