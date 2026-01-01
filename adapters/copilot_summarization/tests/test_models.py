# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for data models."""

from copilot_summarization.models import Citation, Summary, Thread


class TestCitation:
    """Tests for Citation model."""

    def test_citation_creation(self):
        """Test creating a citation."""
        citation = Citation(
            message_id="msg-123",
            chunk_id="chunk-456",
            offset=100
        )

        assert citation.message_id == "msg-123"
        assert citation.chunk_id == "chunk-456"
        assert citation.offset == 100


class TestThread:
    """Tests for Thread model."""

    def test_thread_defaults(self):
        """Test thread with default values."""
        thread = Thread(
            thread_id="thread-123",
            messages=["Message 1", "Message 2"]
        )

        assert thread.thread_id == "thread-123"
        assert len(thread.messages) == 2
        assert thread.top_k == 10
        assert thread.context_window_tokens == 4096
        assert "Summarize" in thread.prompt

    def test_thread_custom_values(self):
        """Test thread with custom values."""
        thread = Thread(
            thread_id="thread-456",
            messages=["Test"],
            top_k=5,
            context_window_tokens=2048,
            prompt="Custom prompt"
        )

        assert thread.thread_id == "thread-456"
        assert thread.top_k == 5
        assert thread.context_window_tokens == 2048
        assert thread.prompt == "Custom prompt"


class TestSummary:
    """Tests for Summary model."""

    def test_summary_defaults(self):
        """Test summary with default values."""
        summary = Summary(
            thread_id="thread-123",
            summary_markdown="# Summary\n\nThis is a test."
        )

        assert summary.thread_id == "thread-123"
        assert summary.summary_markdown == "# Summary\n\nThis is a test."
        assert summary.citations == []
        assert summary.llm_backend == "unknown"
        assert summary.llm_model == "unknown"
        assert summary.tokens_prompt == 0
        assert summary.tokens_completion == 0
        assert summary.latency_ms == 0

    def test_summary_with_citations(self):
        """Test summary with citations."""
        citations = [
            Citation(message_id="msg-1", chunk_id="chunk-1", offset=0),
            Citation(message_id="msg-2", chunk_id="chunk-2", offset=50)
        ]

        summary = Summary(
            thread_id="thread-123",
            summary_markdown="Summary text",
            citations=citations,
            llm_backend="openai",
            llm_model="gpt-4",
            tokens_prompt=100,
            tokens_completion=50,
            latency_ms=1500
        )

        assert len(summary.citations) == 2
        assert summary.llm_backend == "openai"
        assert summary.llm_model == "gpt-4"
        assert summary.tokens_prompt == 100
        assert summary.tokens_completion == 50
        assert summary.latency_ms == 1500
