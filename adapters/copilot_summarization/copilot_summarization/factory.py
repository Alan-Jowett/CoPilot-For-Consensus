# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating summarizer (LLM backend) instances."""

from __future__ import annotations

import logging
from typing import TypeAlias

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.llm_backend import (
    AdapterConfig_LlmBackend,
    DriverConfig_LlmBackend_AzureOpenaiGpt,
    DriverConfig_LlmBackend_Llamacpp,
    DriverConfig_LlmBackend_Local,
    DriverConfig_LlmBackend_Mock,
    DriverConfig_LlmBackend_Openai,
)

from .llamacpp_summarizer import LlamaCppSummarizer
from .local_llm_summarizer import LocalLLMSummarizer
from .mock_summarizer import MockSummarizer
from .openai_summarizer import OpenAISummarizer
from .summarizer import Summarizer

logger = logging.getLogger(__name__)


_DriverConfig: TypeAlias = (
    DriverConfig_LlmBackend_AzureOpenaiGpt
    | DriverConfig_LlmBackend_Llamacpp
    | DriverConfig_LlmBackend_Local
    | DriverConfig_LlmBackend_Mock
    | DriverConfig_LlmBackend_Openai
)


def _build_openai(driver_config: _DriverConfig) -> Summarizer:
    if isinstance(driver_config, DriverConfig_LlmBackend_Openai | DriverConfig_LlmBackend_AzureOpenaiGpt):
        return OpenAISummarizer.from_config(driver_config)
    raise TypeError(f"Expected openai/azure_openai_gpt config, got {type(driver_config).__name__}")


def _build_local(driver_config: _DriverConfig) -> Summarizer:
    if isinstance(driver_config, DriverConfig_LlmBackend_Local):
        return LocalLLMSummarizer.from_config(driver_config)
    raise TypeError(f"Expected local config, got {type(driver_config).__name__}")


def _build_llamacpp(driver_config: _DriverConfig) -> Summarizer:
    if isinstance(driver_config, DriverConfig_LlmBackend_Llamacpp):
        return LlamaCppSummarizer.from_config(driver_config)
    raise TypeError(f"Expected llamacpp config, got {type(driver_config).__name__}")


def _build_mock(driver_config: _DriverConfig) -> Summarizer:
    if isinstance(driver_config, DriverConfig_LlmBackend_Mock):
        return MockSummarizer.from_config(driver_config)
    raise TypeError(f"Expected mock config, got {type(driver_config).__name__}")


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
            "openai": _build_openai,
            "azure_openai_gpt": _build_openai,
            "local": _build_local,
            "llamacpp": _build_llamacpp,
            "mock": _build_mock,
        },
    )
