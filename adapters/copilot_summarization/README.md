<!-- SPDX-License-Identifier: MIT
    Copyright (c) 2025 Copilot-for-Consensus contributors -->

# copilot-summarization

LLM summarization adapter library with support for multiple providers (OpenAI, Azure OpenAI, local models).

## Overview

`copilot-summarization` provides a clean abstraction layer for LLM-based summarization, enabling seamless switching between different providers without changing application logic.

## Features

- **Multiple Provider Support**: OpenAI, Azure OpenAI, local models (Ollama, llama.cpp)
- **Azure OpenAI Integration**: Full support for Azure-hosted models with deployment names and API versioning
- **Token Tracking**: Automatic tracking of prompt and completion tokens for cost monitoring
- **Factory Pattern**: Easy provider selection via environment variables
- **Mock Implementation**: Testing without external API calls
- **Extensible**: Simple interface for adding new providers

## Installation

```bash
pip install ./adapters/copilot_summarization
```

### Optional Dependencies

For OpenAI and Azure OpenAI support:

```bash
pip install "./adapters/copilot_summarization[openai]"
```

## Usage

```python
from copilot_summarization import create_llm_backend, Thread

# Create summarizer
summarizer = create_llm_backend(
    driver_name="openai",
    driver_config={
        "openai_api_key": "your-api-key",
        "openai_model": "gpt-4",
    },
)

# Create a thread to summarize
thread = Thread(
    thread_id="thread-123",
    messages=["Message 1", "Message 2", "Message 3"]
)

# Generate summary
summary = summarizer.summarize(thread)
print(summary.summary_markdown)
```

## Configuration

### Environment Variables

- `SUMMARIZATION_LLM_BACKEND`: Provider type (`openai`, `azure`, `local`, `llamacpp`, `mock`)
- `SUMMARIZATION_LLM_MODEL`: Model name (used by OpenAI/Azure/local/llamacpp)
- `SUMMARIZATION_OPENAI_BASE_URL`: Optional OpenAI-compatible base URL
- `SUMMARIZATION_AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint URL
- `SUMMARIZATION_AZURE_OPENAI_DEPLOYMENT`: Azure deployment name (optional, defaults to model name)
- `SUMMARIZATION_AZURE_OPENAI_API_VERSION`: Azure API version (default: `2023-12-01`)
- `SUMMARIZATION_LOCAL_LLM_ENDPOINT`: Local LLM endpoint (default: `http://ollama:11434`)
- `SUMMARIZATION_LLAMACPP_ENDPOINT`: llama.cpp endpoint (default: `http://llama-cpp:8081`)
- `SUMMARIZATION_LLM_TIMEOUT_SECONDS`: Timeout for local/llamacpp backends (default: `300`)
- `SUMMARIZATION_MOCK_LATENCY_MS`: Mock provider latency (default: `100`)

## Providers

### OpenAI

```python
summarizer = create_llm_backend(
    driver_name="openai",
    driver_config={
        "openai_api_key": "sk-...",
        "openai_model": "gpt-4",
    },
)
```

### Azure OpenAI

```python
summarizer = create_llm_backend(
    driver_name="azure",
    driver_config={
        "azure_openai_api_key": "your-azure-key",
        "azure_openai_endpoint": "https://your-resource.openai.azure.com/",
        "azure_openai_model": "gpt-4",
        "azure_openai_deployment": "gpt-4-deployment",  # Optional
        "azure_openai_api_version": "2023-12-01",  # Optional
    },
)
```

**Azure OpenAI Configuration:**
- `api_key`: Your Azure OpenAI API key
- `base_url`: Azure OpenAI endpoint URL (e.g., `https://your-resource.openai.azure.com`)
- `model`: Model name (e.g., `gpt-4`, `gpt-3.5-turbo`)
- `deployment_name`: (Optional) Azure deployment name, defaults to `model` if not specified
- `api_version`: (Optional) Azure OpenAI API version, defaults to `2023-12-01`

**Note:** Azure OpenAI uses deployment names instead of model names in the API URL. The adapter automatically handles this difference.

### Local LLM

```python
summarizer = create_llm_backend(
    driver_name="local",
    driver_config={
        "local_llm_model": "mistral",
        "local_llm_endpoint": "http://localhost:11434",
    },
)
```

### Mock (for testing)

```python
summarizer = create_llm_backend(driver_name="mock", driver_config={})
```

## Development

### Running Tests

```bash
cd adapters/copilot_summarization
pytest tests/
```

### With Coverage

```bash
pytest tests/ --cov=copilot_summarization --cov-report=html
```

## Architecture

The library follows a clean adapter pattern:

- `Summarizer`: Abstract base class defining the interface
- `OpenAISummarizer`: OpenAI/Azure OpenAI implementation with full API integration
  - Supports both OpenAI and Azure OpenAI endpoints
  - Tracks token usage for cost monitoring
  - Handles Azure-specific deployment names and API versioning
- `LocalLLMSummarizer`: Local LLM implementation (Ollama)
- `LlamaCppSummarizer`: llama.cpp server implementation
- `MockSummarizer`: Mock implementation for testing
- `create_llm_backend`: Factory function for creating summarizer instances
- `Thread`, `Summary`, `Citation`: Data models

## License

MIT License - see LICENSE file for details.
