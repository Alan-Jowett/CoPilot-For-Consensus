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

    def test_openai_rate_limit_error_with_retry(self, mock_openai_module):
        """Test OpenAI summarizer handles rate limit errors with retry."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock rate limit error on first attempt
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.__class__.__name__ = "RateLimitError"

        # Mock successful response on second attempt
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Success after retry"))]
        mock_response.usage = Mock(prompt_tokens=50, completion_tokens=15)

        # First call raises rate limit error, second succeeds
        mock_client.chat.completions.create = Mock(side_effect=[rate_limit_error, mock_response])

        with patch.dict("sys.modules", {"openai": mock_module}):
            summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4", max_retries=3, base_backoff_seconds=0.1)

            complete_prompt = "Test prompt"
            thread = Thread(thread_id="test-thread-123", messages=["Message 1"], prompt=complete_prompt)

            # Should succeed on retry
            summary = summarizer.summarize(thread)

            # Verify API was called twice (initial + 1 retry)
            assert mock_client.chat.completions.create.call_count == 2
            assert summary.summary_markdown == "Success after retry"

    def test_openai_rate_limit_error_exhausted(self, mock_openai_module):
        """Test OpenAI summarizer raises RateLimitError after max retries."""
        from copilot_summarization.openai_summarizer import RateLimitError

        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock rate limit error on all attempts
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.__class__.__name__ = "RateLimitError"

        mock_client.chat.completions.create = Mock(side_effect=rate_limit_error)

        with patch.dict("sys.modules", {"openai": mock_module}):
            summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4", max_retries=2, base_backoff_seconds=0.01)

            complete_prompt = "Test prompt"
            thread = Thread(thread_id="test-thread-123", messages=["Message 1"], prompt=complete_prompt)

            # Should raise RateLimitError after exhausting retries
            with pytest.raises(RateLimitError) as exc_info:
                summarizer.summarize(thread)

            assert "Rate limit exceeded after" in str(exc_info.value)
            # Should have tried: initial + 2 retries = 3 attempts
            assert mock_client.chat.completions.create.call_count == 3

    def test_openai_rate_limit_with_retry_after_header(self, mock_openai_module):
        """Test OpenAI summarizer respects retry-after header."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock rate limit error with retry-after header
        rate_limit_error = Exception("Rate limit exceeded")
        rate_limit_error.__class__.__name__ = "RateLimitError"
        mock_response_obj = Mock()
        mock_response_obj.headers = {"retry-after": "2"}
        rate_limit_error.response = mock_response_obj

        # Mock successful response on second attempt
        mock_success = Mock()
        mock_success.choices = [Mock(message=Mock(content="Success after retry"))]
        mock_success.usage = Mock(prompt_tokens=50, completion_tokens=15)

        mock_client.chat.completions.create = Mock(side_effect=[rate_limit_error, mock_success])

        with patch.dict("sys.modules", {"openai": mock_module}):
            summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4", max_retries=3, base_backoff_seconds=1)

            complete_prompt = "Test prompt"
            thread = Thread(thread_id="test-thread-123", messages=["Message 1"], prompt=complete_prompt)

            # Should succeed on retry
            summary = summarizer.summarize(thread)

            assert mock_client.chat.completions.create.call_count == 2
            assert summary.summary_markdown == "Success after retry"

    def test_openai_non_rate_limit_error_propagates(self, mock_openai_module):
        """Test non-rate-limit errors are propagated without retry."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock a non-rate-limit error (e.g., authentication error)
        auth_error = Exception("Invalid API key")

        mock_client.chat.completions.create = Mock(side_effect=auth_error)

        with patch.dict("sys.modules", {"openai": mock_module}):
            summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4", max_retries=3, base_backoff_seconds=0.1)

            complete_prompt = "Test prompt"
            thread = Thread(thread_id="test-thread-123", messages=["Message 1"], prompt=complete_prompt)

            # Should raise the original error without retrying
            with pytest.raises(Exception) as exc_info:
                summarizer.summarize(thread)

            assert "Invalid API key" in str(exc_info.value)
            # Should only try once (no retries for non-rate-limit errors)
            assert mock_client.chat.completions.create.call_count == 1

    def test_openai_initialization_without_library(self):
        """Test that initialization fails without openai library."""
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError) as exc_info:
                OpenAISummarizer(api_key="test-key")

            assert "openai is required" in str(exc_info.value)
