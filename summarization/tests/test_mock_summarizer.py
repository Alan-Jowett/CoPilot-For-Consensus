# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for MockSummarizer."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.mock_summarizer import MockSummarizer
from adapters.models import Thread


class TestMockSummarizer:
    """Tests for MockSummarizer implementation."""
    
    def test_mock_summarizer_creation(self):
        """Test creating a mock summarizer."""
        summarizer = MockSummarizer()
        assert summarizer.latency_ms == 100
        
    def test_mock_summarizer_custom_latency(self):
        """Test creating a mock summarizer with custom latency."""
        summarizer = MockSummarizer(latency_ms=50)
        assert summarizer.latency_ms == 50
    
    def test_mock_summarize(self):
        """Test generating a mock summary."""
        summarizer = MockSummarizer(latency_ms=10)
        
        thread = Thread(
            thread_id="test-thread-123",
            messages=["Message 1", "Message 2", "Message 3"]
        )
        
        summary = summarizer.summarize(thread)
        
        assert summary.thread_id == "test-thread-123"
        assert "Mock Summary" in summary.summary_markdown
        assert "3 messages" in summary.summary_markdown
        assert summary.llm_backend == "mock"
        assert summary.llm_model == "mock-model-v1"
        assert summary.tokens_prompt == 50
        assert summary.tokens_completion == 30
        assert summary.latency_ms >= 10
    
    def test_mock_summarize_citations(self):
        """Test that mock summary includes citations."""
        summarizer = MockSummarizer(latency_ms=0)
        
        thread = Thread(
            thread_id="test-thread-456",
            messages=["Message 1"]
        )
        
        summary = summarizer.summarize(thread)
        
        assert len(summary.citations) == 1
        assert summary.citations[0].message_id == "msg_test-thread-456_1"
        assert summary.citations[0].chunk_id == "chunk_test-thread-456_1"
        assert summary.citations[0].offset == 0
    
    def test_mock_summarize_empty_thread(self):
        """Test summarizing an empty thread."""
        summarizer = MockSummarizer(latency_ms=0)
        
        thread = Thread(
            thread_id="empty-thread",
            messages=[]
        )
        
        summary = summarizer.summarize(thread)
        
        assert summary.thread_id == "empty-thread"
        assert "0 messages" in summary.summary_markdown
        assert len(summary.citations) == 0
