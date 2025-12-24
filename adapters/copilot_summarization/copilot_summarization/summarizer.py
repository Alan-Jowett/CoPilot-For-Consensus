# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract base class for summarization engines."""

from abc import ABC, abstractmethod

from .models import Summary, Thread


class Summarizer(ABC):
    """Abstract base class for LLM-based summarization engines.

    This interface allows switching between different LLM providers
    (OpenAI, Azure OpenAI, Claude, local models) without changing
    the summarization logic.
    """

    @abstractmethod
    def summarize(self, thread: Thread) -> Summary:
        """Generate a summary for the given thread.

        Args:
            thread: Thread data to summarize

        Returns:
            Summary object containing the generated summary and metadata

        Raises:
            Exception: If summarization fails
        """
        pass
