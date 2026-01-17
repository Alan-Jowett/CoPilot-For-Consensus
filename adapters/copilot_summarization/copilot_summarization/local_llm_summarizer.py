# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Local LLM summarization implementation using Ollama."""

import logging
import time

from copilot_config.generated.adapters.llm_backend import DriverConfig_LlmBackend_Local

import requests

from .models import Citation, Summary, Thread
from .summarizer import Summarizer

logger = logging.getLogger(__name__)


class LocalLLMSummarizer(Summarizer):
    """Local LLM-based summarization engine using Ollama.

    This implementation uses local open-source models via Ollama
    or other compatible local inference engines.

    Attributes:
        model: Model name (e.g., "mistral", "llama2")
        base_url: Base URL for local inference endpoint
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        timeout: int
    ):
        """Initialize local LLM summarizer.

        Args:
            model: Local model name
            base_url: Base URL for local inference endpoint
            timeout: Request timeout in seconds

        """

        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        logger.info("Initialized LocalLLMSummarizer with model: %s", model)

    @classmethod
    def from_config(cls, driver_config: DriverConfig_LlmBackend_Local) -> "LocalLLMSummarizer":
        """Create a LocalLLMSummarizer from configuration.

        Configuration defaults are defined in schema:
        docs/schemas/configs/adapters/drivers/llm_backend/llm_local.json

        Args:
            driver_config: DriverConfig with fields:
                    - local_llm_model: Model name (str)
                    - local_llm_endpoint: Base URL for local LLM (str)
                    - local_llm_timeout_seconds: Request timeout (int)

        Returns:
            Configured LocalLLMSummarizer instance
        """
        return cls(
            model=driver_config.local_llm_model,
            base_url=driver_config.local_llm_endpoint,
            timeout=driver_config.local_llm_timeout_seconds,
        )

    def summarize(self, thread: Thread) -> Summary:
        """Generate a summary using local LLM via Ollama API.

        Args:
            thread: Thread data to summarize

        Returns:
            Summary object with generated summary and metadata

        Raises:
            requests.Timeout: If API call exceeds timeout (infrastructure failure)
            requests.ConnectionError: If connection to Ollama fails (infrastructure failure)
            requests.HTTPError: If API returns HTTP error (4xx, 5xx)
            requests.RequestException: If API call fails for other reasons
            ValueError: If response JSON is malformed

        Note:
            Error handling behavior:
            - Empty responses: Returns fallback summary (graceful degradation)
            - Timeouts/Network errors: Raises exception (infrastructure failure - should retry)
            - HTTP errors: Raises exception (server error - should alert)

            Token estimation uses simple word count (len(text.split())), which may
            undercount actual tokens due to subword tokenization. This provides
            order-of-magnitude estimates suitable for monitoring but not billing.
        """
        start_time = time.time()

        logger.info("Summarizing thread %s with local LLM (%s)", thread.thread_id, self.model)

        # Use the fully-constructed prompt from the service layer
        prompt = thread.prompt

        # Estimate prompt tokens (rough approximation)
        tokens_prompt = len(prompt.split())

        try:
            # Call Ollama API
            # API docs: https://github.com/ollama/ollama/blob/main/docs/api.md
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,  # Get complete response at once
                },
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()

            # Parse response
            result = response.json()
            summary_text = result.get("response", "")

            if not summary_text:
                logger.warning("Empty response from Ollama for thread %s", thread.thread_id)
                summary_text = f"Unable to generate summary for thread {thread.thread_id}"
                # Signal failure in metrics with zero completion tokens
                tokens_completion = 0
            else:
                # Estimate completion tokens (word count approximation)
                tokens_completion = len(summary_text.split())

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Create citations (placeholder - would need context chunks to generate real citations)
            citations: list[Citation] = []

            logger.info(
                "Successfully generated summary for thread %s (tokens: %d+%d, latency: %dms)",
                thread.thread_id, tokens_prompt, tokens_completion, latency_ms
            )

            return Summary(
                thread_id=thread.thread_id,
                summary_markdown=summary_text,
                citations=citations,
                llm_backend="local",
                llm_model=self.model,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                latency_ms=latency_ms
            )

        except requests.Timeout:
            logger.error("Timeout calling Ollama API for thread %s (timeout=%ds)",
                        thread.thread_id, self.timeout)
            raise
        except requests.RequestException as e:
            logger.error("Error calling Ollama API for thread %s: %s",
                        thread.thread_id, str(e))
            raise
        except (KeyError, ValueError) as e:
            logger.error("Invalid response from Ollama API for thread %s: %s",
                        thread.thread_id, str(e))
            raise ValueError(f"Invalid Ollama API response: {e}") from e
