# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Summarization service using copilot-summarization adapter library."""

# Export commonly used items from copilot_summarization for convenience
try:
    from copilot_summarization import (
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
except ImportError:
    # copilot_summarization not installed
    pass
