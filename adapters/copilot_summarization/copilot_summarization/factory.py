# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating summarizer (LLM backend) instances."""

from __future__ import annotations

import logging

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.llm_backend import AdapterConfig_LlmBackend

from .llamacpp_summarizer import LlamaCppSummarizer
from .local_llm_summarizer import LocalLLMSummarizer
from .mock_summarizer import MockSummarizer
from .openai_summarizer import OpenAISummarizer
from .summarizer import Summarizer

logger = logging.getLogger(__name__)


def create_llm_backend(
    config: AdapterConfig_LlmBackend,
) -> Summarizer:
    """Create an LLM backend (summarizer) instance.

    The term 'LLM backend' is used because this factory creates summarizers which are
    implementations of language model-based text summarization. All summarizers in this
    module (OpenAI, Azure OpenAI, Local LLM, LlamaCpp, and Mock) are powered by large
    language models, hence they are referred to as 'LLM backends'.

    Args:
        config: Typed AdapterConfig_LlmBackend instance.

    Returns:
        Summarizer instance.

    Raises:
        ValueError: If config is missing or llm_backend_type is unknown.
    """
    logger.info("Creating LLM backend with driver: %s", config.llm_backend_type)

    return create_adapter(
        config,
        adapter_name="llm_backend",
        get_driver_type=lambda c: c.llm_backend_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "openai": OpenAISummarizer.from_config,
            "azure_openai_gpt": OpenAISummarizer.from_config,
            "local": LocalLLMSummarizer.from_config,
            "llamacpp": LlamaCppSummarizer.from_config,
            "mock": MockSummarizer.from_config,
        },
    )
