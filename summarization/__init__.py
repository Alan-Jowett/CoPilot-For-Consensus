# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Summarization service with pluggable LLM backends."""

from .models import Thread, Summary, Citation
from .summarizer import Summarizer
from .openai_summarizer import OpenAISummarizer
from .mock_summarizer import MockSummarizer
from .local_llm_summarizer import LocalLLMSummarizer
from .factory import SummarizerFactory

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
