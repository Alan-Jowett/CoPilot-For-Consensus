# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for OpenAISummarizer."""

from unittest.mock import Mock, patch

import pytest
from copilot_summarization.models import Thread
from copilot_summarization.openai_summarizer import OpenAISummarizer


class TestOpenAISummarizer:
    """Tests for OpenAISummarizer implementation."""

    def test_openai_summarizer_creation(self, mock_openai_module):
        """Test creating an OpenAI summarizer."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict("sys.modules", {"openai": mock_module}):
            summarizer = OpenAISummarizer(api_key="test-key")
            assert summarizer.api_key == "test-key"
            assert summarizer.model == "gpt-3.5-turbo"
            assert summarizer.base_url is None
            assert summarizer.is_azure is False

    def test_openai_summarizer_custom_model(self, mock_openai_module):
        """Test creating an OpenAI summarizer with custom model."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        with patch.dict("sys.modules", {"openai": mock_module}):
            summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4")
            assert summarizer.model == "gpt-4"
            assert summarizer.is_azure is False

    def test_openai_summarize(self, mock_openai_module):
        """Test OpenAI summarize with real API call structure."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock the API response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="This is a test summary from OpenAI."))]
        mock_response.usage = Mock(prompt_tokens=50, completion_tokens=15)

        mock_client.chat.completions.create = Mock(return_value=mock_response)

        with patch.dict("sys.modules", {"openai": mock_module}):
            summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4")

            complete_prompt = (
                "Summarize the following discussion thread:\n\nMessage 1:\nMessage 1\n\nMessage 2:\nMessage 2\n\n"
            )
            thread = Thread(thread_id="test-thread-123", messages=["Message 1", "Message 2"], prompt=complete_prompt)

            summary = summarizer.summarize(thread)

            # Verify API call was made
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args

            assert call_args[1]["model"] == "gpt-4"
            assert call_args[1]["max_tokens"] == thread.context_window_tokens

            # Verify summary
            assert summary.thread_id == "test-thread-123"
            assert summary.summary_markdown == "This is a test summary from OpenAI."
            assert summary.llm_backend == "openai"
            assert summary.llm_model == "gpt-4"
            assert summary.tokens_prompt == 50
            assert summary.tokens_completion == 15
            assert summary.latency_ms >= 0

    def test_openai_initialization_without_library(self):
        """Test that initialization fails without openai library."""
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError) as exc_info:
                OpenAISummarizer(api_key="test-key")

            assert "openai is required" in str(exc_info.value)
