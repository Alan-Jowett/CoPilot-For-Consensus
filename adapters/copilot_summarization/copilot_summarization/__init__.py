# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""LLM summarization adapters for multiple providers."""

from .factory import create_llm_backend
from .models import Citation, Summary, Thread
from .openai_summarizer import RateLimitError
from .summarizer import Summarizer

__all__ = [
    "Thread",
    "Summary",
    "Citation",
    "Summarizer",
    "RateLimitError",
    "create_llm_backend",
]
