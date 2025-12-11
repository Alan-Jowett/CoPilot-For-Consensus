# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for OpenAISummarizer."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai_summarizer import OpenAISummarizer
from models import Thread


class TestOpenAISummarizer:
    """Tests for OpenAISummarizer implementation."""
    
    def test_openai_summarizer_creation(self):
        """Test creating an OpenAI summarizer."""
        summarizer = OpenAISummarizer(api_key="test-key")
        assert summarizer.api_key == "test-key"
        assert summarizer.model == "gpt-3.5-turbo"
        assert summarizer.base_url is None
    
    def test_openai_summarizer_custom_model(self):
        """Test creating an OpenAI summarizer with custom model."""
        summarizer = OpenAISummarizer(
            api_key="test-key",
            model="gpt-4",
            base_url="https://custom.openai.com"
        )
        assert summarizer.model == "gpt-4"
        assert summarizer.base_url == "https://custom.openai.com"
    
    def test_openai_summarize_placeholder(self):
        """Test OpenAI summarize returns placeholder (no API call)."""
        summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4")
        
        thread = Thread(
            thread_id="test-thread-123",
            messages=["Message 1", "Message 2"]
        )
        
        summary = summarizer.summarize(thread)
        
        assert summary.thread_id == "test-thread-123"
        assert "OpenAI Summary Placeholder" in summary.summary_markdown
        assert summary.llm_backend == "openai"
        assert summary.llm_model == "gpt-4"
        assert summary.tokens_prompt > 0
        assert summary.tokens_completion > 0
        assert summary.latency_ms >= 0
