# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""OpenAI/Azure OpenAI summarization implementation."""

import importlib
import logging
import random
import time
from typing import Any

from copilot_config.generated.adapters.llm_backend import (
    DriverConfig_LlmBackend_AzureOpenaiGpt,
    DriverConfig_LlmBackend_Openai,
)

from .models import Citation, Summary, Thread
from .summarizer import Summarizer

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Exception raised when hitting API rate limits.

    Attributes:
        retry_after: Suggested retry delay in seconds from the API
        status_code: HTTP status code (typically 429)
        message: Error message from the API
    """

    def __init__(self, message: str, retry_after: int | None = None, status_code: int = 429):
        """Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Suggested retry delay in seconds
            status_code: HTTP status code
        """
        super().__init__(message)
        self.retry_after = retry_after
        self.status_code = status_code
        self.message = message


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
        max_retries: Maximum number of retries for rate limit errors (default: 3)
        base_backoff_seconds: Base backoff interval for retries (default: 5)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        base_url: str | None = None,
        api_version: str | None = None,
        deployment_name: str | None = None,
        max_retries: int = 3,
        base_backoff_seconds: int = 5,
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
            max_retries: Maximum number of retries for rate limit errors (default: 3)
            base_backoff_seconds: Base backoff interval for retries (default: 5)

        Note:
            Azure mode is automatically detected based on the presence of base_url.
            When base_url is provided, the Azure OpenAI client is used with the
            specified (or default) api_version and deployment_name.
        """
        try:
            openai_module = importlib.import_module("openai")
        except ImportError as exc:
            raise ImportError(
                "openai is required for OpenAISummarizer. " "Install it with: pip install openai"
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
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds

        # If a deployment_name is provided, an api_version must also be supplied
        # to avoid enabling Azure mode with an incomplete configuration.
        if deployment_name is not None and api_version is None:
            raise ValueError("Azure OpenAI configuration requires 'api_version' when " "'deployment_name' is provided.")

        # Azure mode is enabled only when an explicit Azure api_version is set.
        # Both deployment_name and api_version are required together to configure
        # Azure OpenAI properly, but is_azure status is determined by api_version presence.
        self.is_azure = api_version is not None

        if self.is_azure:
            if not base_url:
                raise ValueError(
                    "Azure OpenAI requires a base_url (azure endpoint). " "Provide the Azure OpenAI endpoint URL."
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
            # TODO: Add max_retries and base_backoff_seconds to config schema
            # for runtime configuration of rate limit retry behavior
            return cls(
                api_key=driver_config.azure_openai_api_key,
                model=driver_config.azure_openai_model,
                base_url=driver_config.azure_openai_endpoint,
                api_version=driver_config.azure_openai_api_version,
                deployment_name=driver_config.azure_openai_deployment,
            )

        # TODO: Add max_retries and base_backoff_seconds to config schema
        # for runtime configuration of rate limit retry behavior
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

    def _is_rate_limit_error(self, exception: Exception) -> tuple[bool, int | None]:
        """Check if an exception is a rate limit error and extract retry-after if available.

        Args:
            exception: Exception to check

        Returns:
            Tuple of (is_rate_limit, retry_after_seconds)
            - is_rate_limit: True if this is a 429 rate limit error
            - retry_after_seconds: Suggested retry delay from API, or None
        """
        # Check for OpenAI's RateLimitError (from openai library)
        if type(exception).__name__ == "RateLimitError":
            # Extract retry-after from exception if available
            # The OpenAI library may include this in the response headers
            retry_after = None
            if hasattr(exception, "response") and exception.response is not None:
                headers = getattr(exception.response, "headers", {})
                if isinstance(headers, dict):
                    # Azure OpenAI uses 'retry-after-ms' or 'retry-after' header
                    retry_after_ms = headers.get("retry-after-ms")
                    retry_after_sec = headers.get("retry-after")
                    if retry_after_ms:
                        try:
                            retry_after = int(retry_after_ms) / 1000
                        except (ValueError, TypeError):
                            pass
                    elif retry_after_sec:
                        try:
                            retry_after = int(retry_after_sec)
                        except (ValueError, TypeError):
                            pass
            return True, retry_after

        # Check for generic API error with status code 429
        if hasattr(exception, "status_code") and getattr(exception, "status_code", None) == 429:
            return True, None

        # Check error message for rate limit indicators
        error_msg = str(exception).lower()
        # Check for common rate limit patterns:
        # - Status code "429"
        # - "rate limit" phrase
        # - "RateLimitReached" (Azure error code, case-insensitive with underscores/spaces removed)
        if "429" in error_msg or "rate limit" in error_msg:
            return True, None
        # Check for RateLimitReached without spaces/underscores
        if "ratelimitreached" in error_msg.replace("_", "").replace(" ", ""):
            return True, None

        return False, None

    def _calculate_backoff_with_jitter(self, attempt: int, retry_after: int | None = None) -> float:
        """Calculate backoff delay with exponential backoff and full jitter.

        Args:
            attempt: Current retry attempt (1-indexed)
            retry_after: Suggested retry delay from API (if available)

        Returns:
            Delay in seconds (float)
        """
        # Jitter multiplier for retry-after to avoid thundering herd
        # Azure may return the same retry-after to many clients simultaneously
        RETRY_AFTER_JITTER_FACTOR = 1.5

        if retry_after is not None and retry_after > 0:
            # Respect the API's suggested retry-after, but add some jitter to avoid thundering herd
            # Use retry_after as the maximum and apply jitter
            base_delay = retry_after
            # Apply jitter factor, capped at 2 minutes to prevent excessive delays
            max_delay = min(retry_after * RETRY_AFTER_JITTER_FACTOR, 120)
        else:
            # Exponential backoff: base * 2^(attempt-1)
            base_delay = self.base_backoff_seconds * (2 ** (attempt - 1))
            max_delay = min(base_delay, 120)  # Cap at 2 minutes

        # Apply full jitter: random value between 0 and calculated delay
        delay = random.uniform(0, max_delay)

        logger.debug(
            "Calculated backoff delay: %.2f seconds (attempt=%d, retry_after=%s, base_delay=%.2f)",
            delay,
            attempt,
            retry_after,
            base_delay,
        )

        return delay

    def summarize(self, thread: Thread) -> Summary:
        """Generate a summary using OpenAI API with rate limit handling.

        Args:
            thread: Thread data to summarize

        Returns:
            Summary object with generated summary and metadata

        Raises:
            RateLimitError: If rate limit is exceeded after all retries
            Exception: If API call fails for other reasons
        """
        start_time = time.time()

        logger.info("Summarizing thread %s with %s", thread.thread_id, "Azure OpenAI" if self.is_azure else "OpenAI")

        # Use the fully-constructed prompt from the service layer
        prompt = thread.prompt

        last_exception = None
        retry_count = 0

        while retry_count <= self.max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.effective_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=thread.context_window_tokens,
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

                logger.info(
                    "Successfully generated summary for thread %s (prompt_tokens=%d, completion_tokens=%d, retries=%d)",
                    thread.thread_id,
                    tokens_prompt,
                    tokens_completion,
                    retry_count,
                )

                latency_ms = int((time.time() - start_time) * 1000)

                # TODO: Implement citation extraction from summary_text
                # Citation extraction requires:
                # 1. Define a structured format for citations in the LLM prompt
                # 2. Parse summary_text to extract citation markers and references
                # 3. Map extracted citations to Citation objects with message_id, chunk_id, offset
                # For now, return empty list so consumers can rely on citations field always being present
                citations: list[Citation] = []

                backend = "azure" if self.is_azure else "openai"

                return Summary(
                    thread_id=thread.thread_id,
                    summary_markdown=summary_text,
                    citations=citations,
                    llm_backend=backend,
                    llm_model=self.effective_model,
                    tokens_prompt=tokens_prompt,
                    tokens_completion=tokens_completion,
                    latency_ms=latency_ms,
                )

            except (IndexError, AttributeError) as e:
                # API response structure unexpected (empty choices or missing attributes)
                # These are not retryable errors
                logger.error("Unexpected API response structure for thread %s: %s", thread.thread_id, str(e))
                raise

            except Exception as e:
                last_exception = e

                # Check if this is a rate limit error
                is_rate_limit, retry_after = self._is_rate_limit_error(e)

                if is_rate_limit and retry_count < self.max_retries:
                    retry_count += 1
                    backoff_delay = self._calculate_backoff_with_jitter(retry_count, retry_after)

                    logger.warning(
                        "Rate limit error for thread %s (attempt %d/%d): %s. "
                        "Retrying after %.2f seconds (suggested retry_after: %s)",
                        thread.thread_id,
                        retry_count,
                        self.max_retries + 1,
                        str(e),
                        backoff_delay,
                        retry_after,
                    )

                    time.sleep(backoff_delay)
                    continue

                # Not a rate limit error or retries exhausted
                if is_rate_limit:
                    logger.error(
                        "Rate limit retries exhausted for thread %s after %d attempts: %s",
                        thread.thread_id,
                        retry_count + 1,
                        str(e),
                    )
                    # Raise a custom RateLimitError to help callers distinguish this from other errors
                    raise RateLimitError(
                        message=f"Rate limit exceeded after {retry_count + 1} attempts: {str(e)}",
                        retry_after=retry_after,
                    ) from e
                else:
                    # Other error - log and re-raise
                    logger.error("Failed to generate summary for thread %s: %s", thread.thread_id, str(e))
                    raise

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in summarize retry loop")
