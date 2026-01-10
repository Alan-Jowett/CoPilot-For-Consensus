# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Mock summarization implementation for testing."""

import logging
import time

from copilot_config import DriverConfig

from .models import Citation, Summary, Thread
from .summarizer import Summarizer

logger = logging.getLogger(__name__)


class MockSummarizer(Summarizer):
    """Mock summarization engine for testing.

    Returns predictable summaries without calling external APIs.
    Useful for unit tests and development.
    """

    def __init__(self, latency_ms: int = 100):
        """Initialize mock summarizer.

        Args:
            latency_ms: Simulated latency in milliseconds (defaults to 100 ms for backward compatibility)
        """
        self.latency_ms = latency_ms
        logger.info("Initialized MockSummarizer")

    @classmethod
    def from_config(cls, driver_config: DriverConfig) -> "MockSummarizer":
        """Create a MockSummarizer from configuration.
        
        Configuration defaults are defined in schema:
        docs/schemas/configs/adapters/drivers/llm_backend/llm_mock.json
        
        Args:
            driver_config: DriverConfig with field:
                    - mock_latency_ms: Simulated latency in ms
        
        Returns:
            Configured MockSummarizer instance
        """
        return cls(driver_config.mock_latency_ms)

    def summarize(self, thread: Thread) -> Summary:
        """Generate a mock summary.

        Args:
            thread: Thread data to summarize

        Returns:
            Summary object with mock data
        """
        start_time = time.time()

        logger.info("Mock summarizing thread %s", thread.thread_id)

        # Simulate processing delay
        if self.latency_ms > 0:
            time.sleep(self.latency_ms / 1000.0)

        # Generate mock summary
        summary_text = (
            f"# Mock Summary for Thread {thread.thread_id}\n\n"
            f"This is a mock summary generated for testing purposes.\n\n"
            f"The thread contained {len(thread.messages)} messages.\n"
        )

        # Create mock citations
        citations = []
        if thread.messages:
            citations.append(Citation(
                message_id=f"msg_{thread.thread_id}_1",
                chunk_id=f"chunk_{thread.thread_id}_1",
                offset=0
            ))

        actual_latency_ms = int((time.time() - start_time) * 1000)

        return Summary(
            thread_id=thread.thread_id,
            summary_markdown=summary_text,
            citations=citations,
            llm_backend="mock",
            llm_model="mock-model-v1",
            tokens_prompt=50,
            tokens_completion=30,
            latency_ms=actual_latency_ms
        )
