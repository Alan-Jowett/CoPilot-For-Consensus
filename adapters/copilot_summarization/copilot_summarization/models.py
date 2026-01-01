# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Data models for summarization service."""

from dataclasses import dataclass, field


@dataclass
class Citation:
    """Citation linking summary to source material.

    Attributes:
        message_id: ID of the source message
        chunk_id: ID of the chunk within the message
        offset: Character offset within the chunk
    """
    message_id: str
    chunk_id: str
    offset: int


@dataclass
class Thread:
    """Thread data to be summarized.

    Attributes:
        thread_id: Unique identifier for the thread
        messages: List of message contents in the thread
        top_k: Number of top relevant chunks to retrieve
        context_window_tokens: Maximum context window size
        prompt: Complete prompt text ready to send to LLM (with all substitutions and messages)
    """
    thread_id: str
    messages: list[str]
    top_k: int = 10
    context_window_tokens: int = 4096
    prompt: str = "Summarize the following discussion thread:"


@dataclass
class Summary:
    """Summary generated for a thread.

    Attributes:
        thread_id: Thread that was summarized
        summary_markdown: Generated summary in Markdown format
        citations: List of citations linking summary to sources
        llm_backend: LLM backend used (e.g., "openai", "azure", "ollama")
        llm_model: Model used (e.g., "gpt-4", "mistral")
        tokens_prompt: Number of prompt tokens used
        tokens_completion: Number of completion tokens generated
        latency_ms: Generation latency in milliseconds
    """
    thread_id: str
    summary_markdown: str
    citations: list[Citation] = field(default_factory=list)
    llm_backend: str = "unknown"
    llm_model: str = "unknown"
    tokens_prompt: int = 0
    tokens_completion: int = 0
    latency_ms: int = 0
