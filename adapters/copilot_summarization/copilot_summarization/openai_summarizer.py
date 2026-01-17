# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""OpenAI/Azure OpenAI summarization implementation."""

import importlib
import json
import logging
import os
import tempfile
import time

from typing import Any

from copilot_config.generated.adapters.llm_backend import (
    DriverConfig_LlmBackend_AzureOpenaiGpt,
    DriverConfig_LlmBackend_Openai,
)

from .models import Summary, Thread
from .summarizer import Summarizer

logger = logging.getLogger(__name__)


class OpenAISummarizer(Summarizer):
    """OpenAI GPT-based summarization engine.

    This implementation uses OpenAI's API for generating summaries.
    Supports both OpenAI and Azure OpenAI endpoints.

    Attributes:
        api_key: OpenAI API key
        model: Model to use (e.g., "gpt-4", "gpt-3.5-turbo")
        base_url: Optional base URL for Azure OpenAI or custom endpoints
        api_version: API version for Azure OpenAI
        deployment_name: Deployment name for Azure OpenAI
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        base_url: str | None = None,
        api_version: str | None = None,
        deployment_name: str | None = None
    ):
        """Initialize OpenAI summarizer.

        Args:
            api_key: OpenAI API key (or Azure OpenAI key)
            model: Model to use for summarization
            base_url: Optional base URL. If provided, Azure OpenAI client is used.
                     For standard OpenAI, leave as None.
            api_version: API version for Azure OpenAI (e.g., "2023-12-01").
                        Only used when base_url is provided.
            deployment_name: Deployment name for Azure OpenAI.
                           Only used when base_url is provided.
                           Defaults to model name if not specified.

        Note:
            Azure mode is automatically detected based on the presence of base_url.
            When base_url is provided, the Azure OpenAI client is used with the
            specified (or default) api_version and deployment_name.
        """
        try:
            openai_module = importlib.import_module("openai")
        except ImportError as exc:
            raise ImportError(
                "openai is required for OpenAISummarizer. "
                "Install it with: pip install openai"
            ) from exc

        OpenAI: Any = getattr(openai_module, "OpenAI", None)
        AzureOpenAI: Any = getattr(openai_module, "AzureOpenAI", None)
        if OpenAI is None or AzureOpenAI is None:
            raise ImportError(
                "openai is installed but missing expected client classes "
                "(OpenAI/AzureOpenAI). Please upgrade: pip install --upgrade openai"
            )

        self.api_key = api_key
        self.model = model
        self.base_url = base_url

        # If a deployment_name is provided, an api_version must also be supplied
        # to avoid enabling Azure mode with an incomplete configuration.
        if deployment_name is not None and api_version is None:
            raise ValueError(
                "Azure OpenAI configuration requires 'api_version' when "
                "'deployment_name' is provided."
            )

        # Azure mode is enabled only when an explicit Azure api_version is set.
        # Both deployment_name and api_version are required together to configure
        # Azure OpenAI properly, but is_azure status is determined by api_version presence.
        self.is_azure = api_version is not None

        if self.is_azure:
            if not base_url:
                raise ValueError(
                    "Azure OpenAI requires a base_url (azure endpoint). "
                    "Provide the Azure OpenAI endpoint URL."
                )

            logger.info(
                "Initialized OpenAISummarizer with Azure OpenAI deployment: %s",
                deployment_name or model,
            )
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=base_url,
            )
            self.deployment_name = deployment_name or model
        else:
            logger.info("Initialized OpenAISummarizer with OpenAI model: %s", model)
            # OpenAI client supports optional custom base URL.
            if base_url is not None:
                self.client = OpenAI(api_key=api_key, base_url=base_url)
            else:
                self.client = OpenAI(api_key=api_key)

    @classmethod
    def from_config(
        cls,
        driver_config: DriverConfig_LlmBackend_Openai | DriverConfig_LlmBackend_AzureOpenaiGpt,
    ) -> "OpenAISummarizer":
        """Create an OpenAISummarizer from configuration.

        Args:
            driver_config: Typed driver config instance.

        Returns:
            Configured OpenAISummarizer instance.

        """

        if isinstance(driver_config, DriverConfig_LlmBackend_AzureOpenaiGpt):
            return cls(
                api_key=driver_config.azure_openai_api_key,
                model=driver_config.azure_openai_model,
                base_url=driver_config.azure_openai_endpoint,
                api_version=driver_config.azure_openai_api_version,
                deployment_name=driver_config.azure_openai_deployment
            )

        return cls(
            api_key=driver_config.openai_api_key,
            model=driver_config.openai_model,
            base_url=driver_config.openai_base_url,
        )

    @property
    def effective_model(self) -> str:
        """Return the effective model name for API calls.

        Returns deployment_name for Azure, model for standard OpenAI.
        """
        return self.deployment_name if self.is_azure else self.model

    def summarize(self, thread: Thread) -> Summary:
        """Generate a summary using OpenAI API.

        Args:
            thread: Thread data to summarize

        Returns:
            Summary object with generated summary and metadata

        Raises:
            Exception: If API call fails
        """
        start_time = time.time()

        logger.info("Summarizing thread %s with %s",
                   thread.thread_id,
                   "Azure OpenAI" if self.is_azure else "OpenAI")

        # Use the fully-constructed prompt from the service layer
        prompt = thread.prompt

        try:
            response = self.client.chat.completions.create(
                model=self.effective_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=thread.context_window_tokens
            )

            summary_text = response.choices[0].message.content
            if summary_text is None:
                raise AttributeError("OpenAI response message content was None")

            usage = response.usage
            if usage is None:
                tokens_prompt = 0
                tokens_completion = 0
            else:
                tokens_prompt = usage.prompt_tokens
                tokens_completion = usage.completion_tokens

            logger.info("Successfully generated summary for thread %s (prompt_tokens=%d, completion_tokens=%d)",
                       thread.thread_id, tokens_prompt, tokens_completion)

        except (IndexError, AttributeError) as e:
            # API response structure unexpected (empty choices or missing attributes)
            logger.error("Unexpected API response structure for thread %s: %s", thread.thread_id, str(e))
            raise
        except Exception as e:
            # Catch all other exceptions (network errors, API errors, etc.)
            # The OpenAI library raises various exceptions that we let propagate
            # so callers can handle them appropriately (e.g., retry logic)
            logger.error("Failed to generate summary for thread %s: %s", thread.thread_id, str(e))
            raise

        latency_ms = int((time.time() - start_time) * 1000)

        # TODO: Implement citation extraction from summary_text
        # Citation extraction requires:
        # 1. Define a structured format for citations in the LLM prompt
        # 2. Parse summary_text to extract citation markers and references
        # 3. Map extracted citations to Citation objects with message_id, chunk_id, offset
        # For now, return empty list so consumers can rely on citations field always being present
        citations = []

        backend = "azure" if self.is_azure else "openai"

        return Summary(
            thread_id=thread.thread_id,
            summary_markdown=summary_text,
            citations=citations,
            llm_backend=backend,
            llm_model=self.effective_model,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            latency_ms=latency_ms
        )

    def create_batch(self, threads: list[Thread]) -> str:
        """Create a batch job for multiple thread summarizations.

        Args:
            threads: List of Thread objects to summarize in batch

        Returns:
            Batch job ID for polling and retrieval

        Raises:
            Exception: If batch creation fails
        """
        start_time = time.time()

        logger.info("Creating batch job for %d threads with %s",
                   len(threads),
                   "Azure OpenAI" if self.is_azure else "OpenAI")

        # Create JSONL file with batch requests
        batch_requests = []
        for thread in threads:
            request = {
                "custom_id": thread.thread_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": self.effective_model,
                    "messages": [{"role": "user", "content": thread.prompt}],
                    "max_tokens": thread.context_window_tokens
                }
            }
            batch_requests.append(request)

        # Write to temporary JSONL file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for request in batch_requests:
                f.write(json.dumps(request) + '\n')
            batch_file_path = f.name

        try:
            # Upload the JSONL file
            with open(batch_file_path, 'rb') as f:
                batch_file = self.client.files.create(
                    file=f,
                    purpose="batch"
                )

            logger.info("Uploaded batch file %s for %d threads", batch_file.id, len(threads))

            # Create the batch job
            batch_job = self.client.batches.create(
                input_file_id=batch_file.id,
                endpoint="/v1/chat/completions",
                completion_window="24h"
            )

            logger.info("Created batch job %s for %d threads (duration: %.2fs)",
                       batch_job.id, len(threads), time.time() - start_time)

            return batch_job.id

        except Exception as e:
            logger.error("Failed to create batch job: %s", str(e))
            raise
        finally:
            # Clean up temporary file
            try:
                os.unlink(batch_file_path)
            except Exception:
                pass

    def get_batch_status(self, batch_id: str) -> dict[str, Any]:
        """Get the status of a batch job.

        Args:
            batch_id: The batch job ID

        Returns:
            Dictionary with status information including:
            - status: "validating", "in_progress", "finalizing", "completed", "failed", "expired", "cancelling", "cancelled"
            - request_counts: dict with total, completed, failed counts
            - output_file_id: ID of output file (if completed)
            - error_file_id: ID of error file (if any errors)

        Raises:
            Exception: If status retrieval fails
        """
        try:
            batch_job = self.client.batches.retrieve(batch_id)

            status_info = {
                "status": batch_job.status,
                "request_counts": {
                    "total": batch_job.request_counts.total,
                    "completed": batch_job.request_counts.completed,
                    "failed": batch_job.request_counts.failed
                }
            }

            if batch_job.output_file_id:
                status_info["output_file_id"] = batch_job.output_file_id

            if batch_job.error_file_id:
                status_info["error_file_id"] = batch_job.error_file_id

            return status_info

        except Exception as e:
            logger.error("Failed to get batch status for %s: %s", batch_id, str(e))
            raise

    def retrieve_batch_results(self, batch_id: str) -> list[Summary]:
        """Retrieve results from a completed batch job.

        Args:
            batch_id: The batch job ID

        Returns:
            List of Summary objects, one per thread in the original batch

        Raises:
            Exception: If batch is not completed or retrieval fails
        """
        start_time = time.time()

        logger.info("Retrieving results for batch job %s", batch_id)

        try:
            # Get batch job details
            batch_job = self.client.batches.retrieve(batch_id)

            if batch_job.status != "completed":
                raise RuntimeError(f"Batch job {batch_id} is not completed (status: {batch_job.status})")

            if not batch_job.output_file_id:
                raise RuntimeError(f"Batch job {batch_id} has no output file")

            # Download the output file
            output_content = self.client.files.content(batch_job.output_file_id)
            output_text = output_content.read()

            # Parse JSONL output
            summaries = []
            backend = "azure" if self.is_azure else "openai"

            for line in output_text.decode('utf-8').strip().split('\n'):
                if not line.strip():
                    continue

                result = json.loads(line)
                thread_id = result["custom_id"]
                response_body = result["response"]["body"]

                # Extract summary text
                summary_text = response_body["choices"][0]["message"]["content"]
                if summary_text is None:
                    logger.warning("Batch result for thread %s has no content", thread_id)
                    summary_text = ""

                # Extract token usage
                usage = response_body.get("usage", {})
                tokens_prompt = usage.get("prompt_tokens", 0)
                tokens_completion = usage.get("completion_tokens", 0)

                # Create Summary object
                summary = Summary(
                    thread_id=thread_id,
                    summary_markdown=summary_text,
                    citations=[],
                    llm_backend=backend,
                    llm_model=self.effective_model,
                    tokens_prompt=tokens_prompt,
                    tokens_completion=tokens_completion,
                    latency_ms=0  # Batch mode doesn't track per-request latency
                )
                summaries.append(summary)

            logger.info("Retrieved %d summaries from batch job %s (duration: %.2fs)",
                       len(summaries), batch_id, time.time() - start_time)

            return summaries

        except Exception as e:
            logger.error("Failed to retrieve batch results for %s: %s", batch_id, str(e))
            raise
