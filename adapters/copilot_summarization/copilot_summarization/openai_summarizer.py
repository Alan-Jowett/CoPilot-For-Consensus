# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""OpenAI/Azure OpenAI summarization implementation."""

import logging
import time

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
            from openai import AzureOpenAI, OpenAI
        except ImportError:
            raise ImportError(
                "openai is required for OpenAISummarizer. "
                "Install it with: pip install openai"
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
