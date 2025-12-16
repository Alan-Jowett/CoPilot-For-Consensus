# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Local LLM summarization implementation using Ollama."""

import time
import logging
import requests
try:
    from summarizer import Summarizer
    from models import Thread, Summary
except ImportError:
    from .summarizer import Summarizer
    from .models import Thread, Summary

logger = logging.getLogger(__name__)


class LocalLLMSummarizer(Summarizer):
    """Local LLM-based summarization engine using Ollama.
    
    This implementation uses local open-source models via Ollama
    or other compatible local inference engines.
    
    Attributes:
        model: Model name (e.g., "mistral", "llama2")
        base_url: Base URL for local inference endpoint
        timeout: Request timeout in seconds
    """
    
    def __init__(
        self,
        model: str = "mistral",
        base_url: str = "http://localhost:11434",
        timeout: int = 120
    ):
        """Initialize local LLM summarizer.
        
        Args:
            model: Local model name
            base_url: Base URL for local inference endpoint (e.g., Ollama)
            timeout: Request timeout in seconds (default: 120)
        """
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        logger.info("Initialized LocalLLMSummarizer with model: %s", model)
        
    def summarize(self, thread: Thread) -> Summary:
        """Generate a summary using local LLM via Ollama API.
        
        Args:
            thread: Thread data to summarize
            
        Returns:
            Summary object with generated summary and metadata
            
        Raises:
            requests.RequestException: If API call fails
            ValueError: If response is invalid
        """
        start_time = time.time()
        
        logger.info("Summarizing thread %s with local LLM (%s)", thread.thread_id, self.model)
        
        # Construct prompt
        prompt = f"{thread.prompt_template}\n\n"
        for i, message in enumerate(thread.messages[:thread.top_k]):
            prompt += f"Message {i+1}:\n{message}\n\n"
        
        # Estimate prompt tokens (rough approximation)
        tokens_prompt = len(prompt.split())
        
        try:
            # Call Ollama API
            # API docs: https://github.com/ollama/ollama/blob/main/docs/api.md
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,  # Get complete response at once
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            summary_text = result.get("response", "")
            
            if not summary_text:
                logger.warning("Empty response from Ollama for thread %s", thread.thread_id)
                summary_text = f"Unable to generate summary for thread {thread.thread_id}"
            
            # Estimate completion tokens
            tokens_completion = len(summary_text.split())
            
            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Create citations (placeholder - would need context chunks to generate real citations)
            citations = []
            
            logger.info(
                "Successfully generated summary for thread %s (tokens: %d+%d, latency: %dms)",
                thread.thread_id, tokens_prompt, tokens_completion, latency_ms
            )
            
            return Summary(
                thread_id=thread.thread_id,
                summary_markdown=summary_text,
                citations=citations,
                llm_backend="local",
                llm_model=self.model,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                latency_ms=latency_ms
            )
            
        except requests.Timeout:
            logger.error("Timeout calling Ollama API for thread %s (timeout=%ds)", 
                        thread.thread_id, self.timeout)
            raise
        except requests.RequestException as e:
            logger.error("Error calling Ollama API for thread %s: %s", 
                        thread.thread_id, str(e))
            raise
        except (KeyError, ValueError) as e:
            logger.error("Invalid response from Ollama API for thread %s: %s", 
                        thread.thread_id, str(e))
            raise ValueError(f"Invalid Ollama API response: {e}") from e
