# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating summarizer (LLM backend) instances."""

from __future__ import annotations

import logging
from typing import Any

from copilot_config import DriverConfig

from .llamacpp_summarizer import LlamaCppSummarizer
from .local_llm_summarizer import LocalLLMSummarizer
from .mock_summarizer import MockSummarizer
from .openai_summarizer import OpenAISummarizer
from .summarizer import Summarizer

logger = logging.getLogger(__name__)


def create_llm_backend(
    driver_name: str,
    driver_config: DriverConfig,
) -> Summarizer:
    """Create an LLM backend (summarizer) instance.

    The term 'LLM backend' is used because this factory creates summarizers which are
    implementations of language model-based text summarization. All summarizers in this
    module (OpenAI, Azure OpenAI, Local LLM, LlamaCpp, and Mock) are powered by large
    language models, hence they are referred to as 'LLM backends'.

    Args:
        driver_name: Backend type (required). Options: "openai", "azure", "local", "llamacpp", "mock".
        driver_config: Backend configuration as DriverConfig instance.

    Returns:
        Summarizer instance.

    Raises:
        ValueError: If driver_name is unknown.
    """
    driver_lower = driver_name.lower()

    logger.info("Creating LLM backend with driver: %s", driver_lower)

    if driver_lower == "openai":
        return OpenAISummarizer.from_config(driver_config)

    if driver_lower == "azure_openai_gpt":
        return OpenAISummarizer.from_config(driver_config)

    if driver_lower == "local":
        return LocalLLMSummarizer.from_config(driver_config)

    if driver_lower == "llamacpp":
        return LlamaCppSummarizer.from_config(driver_config)

    if driver_lower == "mock":
        return MockSummarizer.from_config(driver_config)

    raise ValueError(f"Unknown LLM backend driver: {driver_name}")
