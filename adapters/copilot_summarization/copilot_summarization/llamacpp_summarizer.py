# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""llama.cpp summarization implementation with AMD GPU support."""

import logging
import time

from copilot_config import DriverConfig

import requests

from .models import Summary, Thread
from .summarizer import Summarizer

logger = logging.getLogger(__name__)


class LlamaCppSummarizer(Summarizer):
    """llama.cpp-based summarization engine with AMD GPU support.

    This implementation uses llama.cpp server with Vulkan/OpenCL/ROCm
    backends for AMD GPU acceleration. It provides better AMD GPU
    support compared to Ollama, especially for integrated GPUs.

    Attributes:
        model: Model name (e.g., "mistral-7b-instruct-v0.2.Q4_K_M")
        base_url: Base URL for llama.cpp server endpoint
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        timeout: int
    ):
        """Initialize llama.cpp summarizer.

        Args:
            model: Model name (used for logging and metrics)
            base_url: Base URL for llama.cpp server endpoint
            timeout: Request timeout in seconds

        Raises:
            ValueError: If timeout is not a positive integer
        """
        if not isinstance(timeout, int) or timeout <= 0:
            raise ValueError(f"timeout must be a positive integer, got {timeout!r}")

        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        logger.info("Initialized LlamaCppSummarizer with model: %s", model)

    @classmethod
    def from_config(cls, config: DriverConfig) -> "LlamaCppSummarizer":
        """Create a LlamaCppSummarizer from configuration.

        Configuration defaults are defined in schema:
        docs/schemas/configs/adapters/drivers/llm_backend/llm_llamacpp.json

        Args:
            config: DriverConfig with fields:
                    - llamacpp_model: Model name (str)
                    - llamacpp_endpoint: Base URL for llama.cpp (str)
                    - llamacpp_timeout_seconds: Request timeout (int)

        Returns:
            Configured LlamaCppSummarizer instance
        """
        return cls(
            model=config.llamacpp_model,
            base_url=config.llamacpp_endpoint,
            timeout=config.llamacpp_timeout_seconds,
        )

    def summarize(self, thread: Thread) -> Summary:
        """Generate a summary using llama.cpp server API.

        Args:
            thread: Thread data to summarize

        Returns:
            Summary object with generated summary and metadata

        Raises:
            requests.Timeout: If API call exceeds timeout (infrastructure failure)
            requests.ConnectionError: If connection to llama.cpp fails (infrastructure failure)
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

        logger.info("Summarizing thread %s with llama.cpp (%s)", thread.thread_id, self.model)

        # Use pre-constructed prompt from service layer
        prompt = thread.prompt

        # Estimate prompt tokens (rough approximation)
        tokens_prompt = len(prompt.split())

        try:
            # Call llama.cpp server API
            # API docs: https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md
            response = requests.post(
                f"{self.base_url}/completion",
                json={
                    "prompt": prompt,
                    "n_predict": 512,  # Max tokens to generate
                    "temperature": 0.7,
                    "stop": ["</s>", "\n\n\n"],  # Stop sequences
                },
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()

            # Parse response
            result = response.json()
            summary_text = result.get("content", "")

            if not summary_text:
                logger.warning("Empty response from llama.cpp for thread %s", thread.thread_id)
                summary_text = f"Unable to generate summary for thread {thread.thread_id}"
                # Signal failure in metrics with zero completion tokens
                tokens_completion = 0
            else:
                # Estimate completion tokens (word count approximation)
                tokens_completion = len(summary_text.split())

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Create citations (placeholder - would need context chunks to generate real citations)
            citations = []

            logger.info(
                "Successfully generated summary for thread %s (tokens: %d+%d, latency: %dms)",
                thread.thread_id, tokens_prompt, tokens_completion, latency_ms
            )

            return Summary(
                thread_id=thread.thread_id,
                summary_markdown=summary_text,
                citations=citations,
                llm_backend="llamacpp",
                llm_model=self.model,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                latency_ms=latency_ms
            )

        except requests.Timeout:
            logger.error("Timeout calling llama.cpp API for thread %s (timeout=%ds)",
                        thread.thread_id, self.timeout)
            raise
        except requests.RequestException as e:
            logger.error("Error calling llama.cpp API for thread %s: %s",
                        thread.thread_id, str(e))
            raise
        except (KeyError, ValueError) as e:
            logger.error("Invalid response from llama.cpp API for thread %s: %s",
                        thread.thread_id, str(e))
            raise ValueError(f"Invalid llama.cpp API response: {e}") from e
