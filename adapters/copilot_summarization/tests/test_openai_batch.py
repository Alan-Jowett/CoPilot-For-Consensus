# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for OpenAI Batch API functionality."""

from contextlib import contextmanager
from unittest.mock import Mock, patch, mock_open

import pytest
from copilot_summarization.models import Thread
from copilot_summarization.openai_summarizer import OpenAISummarizer


@contextmanager
def mock_tempfile_and_cleanup():
    """Context manager that mocks tempfile creation and cleanup for batch tests."""
    temp_mock = Mock(name='/tmp/test.jsonl')
    temp_mock.__enter__ = Mock(return_value=temp_mock)
    temp_mock.__exit__ = Mock()
    temp_mock.write = Mock()
    
    with patch('builtins.open', mock_open()):
        with patch('tempfile.NamedTemporaryFile', return_value=temp_mock):
            with patch('os.unlink'):
                yield


class TestOpenAIBatchMode:
    """Tests for OpenAI Batch API mode."""

    def test_create_batch(self, mock_openai_module):
        """Test creating a batch job."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock file upload
        mock_file = Mock()
        mock_file.id = "file-abc123"
        mock_client.files.create = Mock(return_value=mock_file)

        # Mock batch creation
        mock_batch = Mock()
        mock_batch.id = "batch-xyz789"
        mock_batch.status = "validating"
        mock_client.batches.create = Mock(return_value=mock_batch)

        with patch.dict('sys.modules', {'openai': mock_module}):
            with mock_tempfile_and_cleanup():
                summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4o-mini")

                threads = [
                    Thread(
                        thread_id="thread-1",
                        messages=["Message 1"],
                        prompt="Summarize: Message 1"
                    ),
                    Thread(
                        thread_id="thread-2",
                        messages=["Message 2"],
                        prompt="Summarize: Message 2"
                    ),
                ]

                batch_id = summarizer.create_batch(threads)

                assert batch_id == "batch-xyz789"
                mock_client.files.create.assert_called_once()
                mock_client.batches.create.assert_called_once()

    def test_get_batch_status(self, mock_openai_module):
        """Test getting batch job status."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock batch status
        mock_batch = Mock()
        mock_batch.status = "completed"
        mock_batch.request_counts = Mock(
            total=2,
            completed=2,
            failed=0
        )
        mock_batch.output_file_id = "file-output-123"
        mock_batch.error_file_id = None
        mock_client.batches.retrieve = Mock(return_value=mock_batch)

        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4o-mini")

            status = summarizer.get_batch_status("batch-xyz789")

            assert status["status"] == "completed"
            assert status["request_counts"]["total"] == 2
            assert status["request_counts"]["completed"] == 2
            assert status["request_counts"]["failed"] == 0
            assert status["output_file_id"] == "file-output-123"

    def test_retrieve_batch_results(self, mock_openai_module):
        """Test retrieving results from a completed batch."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock batch retrieval
        mock_batch = Mock()
        mock_batch.status = "completed"
        mock_batch.output_file_id = "file-output-123"
        mock_client.batches.retrieve = Mock(return_value=mock_batch)

        # Mock file content download
        output_jsonl = '''{"custom_id":"thread-1","response":{"body":{"choices":[{"message":{"content":"Summary 1"}}],"usage":{"prompt_tokens":50,"completion_tokens":20}}}}
{"custom_id":"thread-2","response":{"body":{"choices":[{"message":{"content":"Summary 2"}}],"usage":{"prompt_tokens":55,"completion_tokens":25}}}}'''
        mock_content = Mock()
        mock_content.read = Mock(return_value=output_jsonl.encode('utf-8'))
        mock_client.files.content = Mock(return_value=mock_content)

        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4o-mini")

            summaries = summarizer.retrieve_batch_results("batch-xyz789")

            assert len(summaries) == 2
            assert summaries[0].thread_id == "thread-1"
            assert summaries[0].summary_markdown == "Summary 1"
            assert summaries[0].tokens_prompt == 50
            assert summaries[0].tokens_completion == 20
            assert summaries[1].thread_id == "thread-2"
            assert summaries[1].summary_markdown == "Summary 2"
            assert summaries[1].tokens_prompt == 55
            assert summaries[1].tokens_completion == 25

    def test_retrieve_batch_results_not_completed(self, mock_openai_module):
        """Test that retrieving results fails if batch is not completed."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock batch with in_progress status
        mock_batch = Mock()
        mock_batch.status = "in_progress"
        mock_client.batches.retrieve = Mock(return_value=mock_batch)

        with patch.dict('sys.modules', {'openai': mock_module}):
            summarizer = OpenAISummarizer(api_key="test-key", model="gpt-4o-mini")

            with pytest.raises(RuntimeError, match="not completed"):
                summarizer.retrieve_batch_results("batch-xyz789")

    def test_azure_batch_mode(self, mock_openai_module):
        """Test batch mode with Azure OpenAI."""
        mock_module, mock_client, mock_openai_class, mock_azure_class = mock_openai_module

        # Mock file upload
        mock_file = Mock()
        mock_file.id = "file-abc123"
        mock_client.files.create = Mock(return_value=mock_file)

        # Mock batch creation
        mock_batch = Mock()
        mock_batch.id = "batch-xyz789"
        mock_batch.status = "validating"
        mock_client.batches.create = Mock(return_value=mock_batch)

        with patch.dict('sys.modules', {'openai': mock_module}):
            with mock_tempfile_and_cleanup():
                summarizer = OpenAISummarizer(
                    api_key="azure-key",
                    model="gpt-4o-mini",
                    base_url="https://test.openai.azure.com",
                    api_version="2023-12-01",
                    deployment_name="gpt-4o-mini-deployment"
                )

                threads = [
                    Thread(
                        thread_id="thread-1",
                        messages=["Message 1"],
                        prompt="Summarize: Message 1"
                    ),
                ]

                batch_id = summarizer.create_batch(threads)

                assert batch_id == "batch-xyz789"
                assert summarizer.is_azure is True
