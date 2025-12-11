# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for LocalLLMSummarizer."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from local_llm_summarizer import LocalLLMSummarizer
from models import Thread


class TestLocalLLMSummarizer:
    """Tests for LocalLLMSummarizer implementation."""
    
    def test_local_llm_summarizer_creation(self):
        """Test creating a local LLM summarizer."""
        summarizer = LocalLLMSummarizer()
        assert summarizer.model == "mistral"
        assert summarizer.base_url == "http://localhost:11434"
    
    def test_local_llm_summarizer_custom_config(self):
        """Test creating a local LLM summarizer with custom config."""
        summarizer = LocalLLMSummarizer(
            model="llama2",
            base_url="http://custom:8080"
        )
        assert summarizer.model == "llama2"
        assert summarizer.base_url == "http://custom:8080"
    
    def test_local_llm_summarize_placeholder(self):
        """Test local LLM summarize returns placeholder (no API call)."""
        summarizer = LocalLLMSummarizer(model="mistral")
        
        thread = Thread(
            thread_id="test-thread-123",
            messages=["Message 1", "Message 2"]
        )
        
        summary = summarizer.summarize(thread)
        
        assert summary.thread_id == "test-thread-123"
        assert "Local LLM Summary Placeholder" in summary.summary_markdown
        assert "scaffold implementation" in summary.summary_markdown
        assert summary.llm_backend == "local"
        assert summary.llm_model == "mistral"
        assert summary.tokens_prompt > 0
        assert summary.tokens_completion > 0
        assert summary.latency_ms >= 0
