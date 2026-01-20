# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for context selector implementations."""

from unittest.mock import Mock

import pytest
from app.context_selectors import TopKCohesiveSelector, TopKRelevanceSelector


class TestTopKRelevanceSelector:
    """Tests for TopKRelevanceSelector."""

    def test_select_top_k_by_score(self):
        """Test that selector picks top-k by relevance score."""
        selector = TopKRelevanceSelector()

        candidates = [
            {"_id": "chunk1", "similarity_score": 0.9, "text": "high relevance"},
            {"_id": "chunk2", "similarity_score": 0.5, "text": "medium relevance"},
            {"_id": "chunk3", "similarity_score": 0.8, "text": "good relevance"},
            {"_id": "chunk4", "similarity_score": 0.3, "text": "low relevance"},
        ]

        result = selector.select(thread_id="test-thread", candidates=candidates, top_k=2)

        assert len(result.selected_chunks) == 2
        # Should select chunk1 (0.9) and chunk3 (0.8)
        assert result.selected_chunks[0].chunk_id == "chunk1"
        assert result.selected_chunks[0].score == 0.9
        assert result.selected_chunks[0].rank == 0
        assert result.selected_chunks[1].chunk_id == "chunk3"
        assert result.selected_chunks[1].score == 0.8
        assert result.selected_chunks[1].rank == 1

    def test_deterministic_tie_breaking(self):
        """Test that ties are broken deterministically by chunk_id."""
        selector = TopKRelevanceSelector()

        candidates = [
            {"_id": "chunk_a", "similarity_score": 0.5, "text": "text a"},
            {"_id": "chunk_b", "similarity_score": 0.5, "text": "text b"},
            {"_id": "chunk_c", "similarity_score": 0.5, "text": "text c"},
        ]

        result = selector.select(thread_id="test-thread", candidates=candidates, top_k=2)

        assert len(result.selected_chunks) == 2
        # Should be ordered by chunk_id (alphabetically) when scores are equal
        assert result.selected_chunks[0].chunk_id == "chunk_a"
        assert result.selected_chunks[1].chunk_id == "chunk_b"

    def test_token_budget_enforcement(self):
        """Test that selector respects token budget."""
        selector = TopKRelevanceSelector()

        candidates = [
            {"_id": "chunk1", "similarity_score": 0.9, "text": "a" * 100},  # ~130 tokens
            {"_id": "chunk2", "similarity_score": 0.8, "text": "b" * 100},  # ~130 tokens
            {"_id": "chunk3", "similarity_score": 0.7, "text": "c" * 100},  # ~130 tokens
            {"_id": "chunk4", "similarity_score": 0.6, "text": "d" * 100},  # ~130 tokens
        ]

        # Budget should allow only ~2 chunks
        result = selector.select(
            thread_id="test-thread", candidates=candidates, top_k=4, context_window_tokens=300
        )

        # Should stop at 2 chunks due to token budget
        assert len(result.selected_chunks) <= 3
        assert result.total_tokens <= 300

    def test_empty_candidates(self):
        """Test behavior with empty candidates."""
        selector = TopKRelevanceSelector()

        result = selector.select(thread_id="test-thread", candidates=[], top_k=5)

        assert len(result.selected_chunks) == 0
        assert result.total_candidates == 0

    def test_fewer_candidates_than_top_k(self):
        """Test that selector returns all candidates if fewer than top_k."""
        selector = TopKRelevanceSelector()

        candidates = [
            {"_id": "chunk1", "similarity_score": 0.9, "text": "high"},
            {"_id": "chunk2", "similarity_score": 0.5, "text": "low"},
        ]

        result = selector.select(thread_id="test-thread", candidates=candidates, top_k=10)

        assert len(result.selected_chunks) == 2

    def test_selector_metadata(self):
        """Test that result includes correct selector metadata."""
        selector = TopKRelevanceSelector()

        candidates = [{"_id": "chunk1", "similarity_score": 0.9, "text": "test"}]

        result = selector.select(
            thread_id="test-thread", candidates=candidates, top_k=5, context_window_tokens=1000
        )

        assert result.selector_type == "top_k_relevance"
        assert result.selector_version == "1.0.0"
        assert result.selection_params["top_k"] == 5
        assert result.selection_params["context_window_tokens"] == 1000
        assert result.total_candidates == 1

    def test_chunk_metadata_preservation(self):
        """Test that chunk metadata is preserved in selected chunks."""
        selector = TopKRelevanceSelector()

        candidates = [
            {
                "_id": "chunk1",
                "similarity_score": 0.9,
                "text": "test",
                "message_id": "msg1",
                "message_doc_id": "doc1",
                "offset": 100,
                "thread_id": "thread1",
            }
        ]

        result = selector.select(thread_id="thread1", candidates=candidates, top_k=1)

        assert len(result.selected_chunks) == 1
        selected = result.selected_chunks[0]
        assert selected.metadata["message_id"] == "msg1"
        assert selected.metadata["message_doc_id"] == "doc1"
        assert selected.metadata["offset"] == 100
        assert selected.metadata["thread_id"] == "thread1"


class TestTopKCohesiveSelector:
    """Tests for TopKCohesiveSelector (placeholder implementation)."""

    def test_fallback_to_relevance(self):
        """Test that cohesive selector currently falls back to relevance-based selection."""
        selector = TopKCohesiveSelector()

        candidates = [
            {"_id": "chunk1", "similarity_score": 0.9, "text": "high"},
            {"_id": "chunk2", "similarity_score": 0.5, "text": "low"},
        ]

        result = selector.select(thread_id="test-thread", candidates=candidates, top_k=2)

        # Should behave like relevance selector for now
        assert len(result.selected_chunks) == 2
        assert result.selector_type == "top_k_cohesive"
        assert result.selector_version == "1.0.0"


class TestContextSelectorFactory:
    """Tests for context selector factory."""

    def test_create_top_k_relevance_selector(self):
        """Test creating top-k relevance selector."""
        from app.context_factory import create_context_selector

        selector = create_context_selector("top_k_relevance")

        assert isinstance(selector, TopKRelevanceSelector)
        assert selector.get_selector_type() == "top_k_relevance"

    def test_create_top_k_cohesive_selector(self):
        """Test creating top-k cohesive selector."""
        from app.context_factory import create_context_selector

        selector = create_context_selector("top_k_cohesive")

        assert isinstance(selector, TopKCohesiveSelector)
        assert selector.get_selector_type() == "top_k_cohesive"

    def test_unknown_selector_type(self):
        """Test that unknown selector type raises error."""
        from app.context_factory import create_context_selector

        with pytest.raises(ValueError, match="Unknown selector type"):
            create_context_selector("invalid_selector")


class TestContextSourceFactory:
    """Tests for context source factory."""

    def test_create_thread_chunks_source(self):
        """Test creating thread chunks source."""
        from app.context_factory import create_context_source
        from app.context_sources import ThreadChunksSource

        mock_doc_store = Mock()
        mock_vector_store = Mock()

        source = create_context_source("thread_chunks", mock_doc_store, mock_vector_store)

        assert isinstance(source, ThreadChunksSource)
        assert source.get_source_type() == "thread_chunks"

    def test_missing_vector_store(self):
        """Test that thread_chunks source requires vector store."""
        from app.context_factory import create_context_source

        mock_doc_store = Mock()

        with pytest.raises(ValueError, match="vector_store is required"):
            create_context_source("thread_chunks", mock_doc_store, None)

    def test_unknown_source_type(self):
        """Test that unknown source type raises error."""
        from app.context_factory import create_context_source

        mock_doc_store = Mock()
        mock_vector_store = Mock()

        with pytest.raises(ValueError, match="Unknown source type"):
            create_context_source("invalid_source", mock_doc_store, mock_vector_store)
