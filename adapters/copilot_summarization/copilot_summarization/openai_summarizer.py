# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""OpenAI-based summarization implementation."""

import time
import logging
from typing import Optional
try:
    from summarizer import Summarizer
    from models import Thread, Summary
except ImportError:
    from .summarizer import Summarizer
    from .models import Thread, Summary

logger = logging.getLogger(__name__)

# Default API version for Azure OpenAI
DEFAULT_AZURE_API_VERSION = "2023-12-01"

class OpenAISummarizer(Summarizer):
    """OpenAI GPT-based summarization engine.
    
    This implementation uses OpenAI's API for generating summaries.
    Supports both OpenAI and Azure OpenAI endpoints.
    
    Attributes:
        api_key: OpenAI API key
        model: Model to use (e.g., "gpt-4", "gpt-3.5-turbo")
        base_url: Optional base URL for Azure OpenAI or custom endpoints
        api_version: API version for Azure OpenAI
        deployment_name: Deployment name for Azure OpenAI
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        deployment_name: Optional[str] = None
    ):
        """Initialize OpenAI summarizer.
        
        Args:
            api_key: OpenAI API key (or Azure OpenAI key)
            model: Model to use for summarization
            base_url: Optional base URL. If provided, Azure OpenAI client is used.
                     For standard OpenAI, leave as None.
            api_version: API version for Azure OpenAI (e.g., "2023-12-01").
                        Only used when base_url is provided.
            deployment_name: Deployment name for Azure OpenAI.
                           Only used when base_url is provided.
                           Defaults to model name if not specified.
        
        Note:
            Azure mode is automatically detected based on the presence of base_url.
            When base_url is provided, the Azure OpenAI client is used with the
            specified (or default) api_version and deployment_name.
        """
        try:
            from openai import OpenAI, AzureOpenAI
        except ImportError:
            raise ImportError(
                "openai is required for OpenAISummarizer. "
                "Install it with: pip install openai"
            )
        
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.is_azure = base_url is not None
        
        if self.is_azure:
            logger.info("Initialized OpenAISummarizer with Azure OpenAI deployment: %s", deployment_name or model)
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version or DEFAULT_AZURE_API_VERSION,
                azure_endpoint=base_url
            )
            self.deployment_name = deployment_name or model
        else:
            logger.info("Initialized OpenAISummarizer with OpenAI model: %s", model)
            self.client = OpenAI(api_key=api_key)
        
    def summarize(self, thread: Thread) -> Summary:
        """Generate a summary using OpenAI API.
        
        Args:
            thread: Thread data to summarize
            
        Returns:
            Summary object with generated summary and metadata
            
        Raises:
            Exception: If API call fails
        """
        start_time = time.time()
        
        logger.info("Summarizing thread %s with %s", 
                   thread.thread_id, 
                   "Azure OpenAI" if self.is_azure else "OpenAI")
        
        # Construct prompt
        prompt = f"{thread.prompt_template}\n\n"
        for i, message in enumerate(thread.messages[:thread.top_k]):
            prompt += f"Message {i+1}:\n{message}\n\n"
        
        try:
            # Select model based on backend and call OpenAI or Azure OpenAI API
            model_for_call = self.deployment_name if self.is_azure else self.model
            response = self.client.chat.completions.create(
                model=model_for_call,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=thread.context_window_tokens
            )
            
            summary_text = response.choices[0].message.content
            tokens_prompt = response.usage.prompt_tokens
            tokens_completion = response.usage.completion_tokens
            
            logger.info("Successfully generated summary for thread %s (prompt_tokens=%d, completion_tokens=%d)",
                       thread.thread_id, tokens_prompt, tokens_completion)
        
        except AttributeError as e:
            # API response structure unexpected
            logger.error("Unexpected API response structure for thread %s: %s", thread.thread_id, str(e))
            raise
        except Exception as e:
            # Catch all other exceptions (network errors, API errors, etc.)
            # The OpenAI library raises various exceptions that we let propagate
            # so callers can handle them appropriately (e.g., retry logic)
            logger.error("Failed to generate summary for thread %s: %s", thread.thread_id, str(e))
            raise
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Create citations (placeholder - would need to parse from summary)
        citations = []
        
        backend = "azure" if self.is_azure else "openai"
        model_name = self.deployment_name if self.is_azure else self.model
        
        return Summary(
            thread_id=thread.thread_id,
            summary_markdown=summary_text,
            citations=citations,
            llm_backend=backend,
            llm_model=model_name,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            latency_ms=latency_ms
        )
