# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Summarization service with pluggable LLM adapters."""

from .adapters import (
    Thread,
    Summary,
    Citation,
    Summarizer,
    OpenAISummarizer,
    MockSummarizer,
    LocalLLMSummarizer,
    SummarizerFactory,
)

__all__ = [
    "Thread",
    "Summary",
    "Citation",
    "Summarizer",
    "OpenAISummarizer",
    "MockSummarizer",
    "LocalLLMSummarizer",
    "SummarizerFactory",
]
