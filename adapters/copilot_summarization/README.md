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
from copilot_summarization import SummarizerFactory, Thread

# Create summarizer (defaults to mock provider)
summarizer = SummarizerFactory.create_summarizer()

# Or specify a provider
summarizer = SummarizerFactory.create_summarizer(
    provider="openai",
    api_key="your-api-key",
    model="gpt-4"
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

- `SUMMARIZER_PROVIDER`: Provider type (`openai`, `azure`, `local`, `llamacpp`, `mock`)
- `OPENAI_API_KEY`: OpenAI API key
- `OPENAI_MODEL`: OpenAI model to use (default: `gpt-3.5-turbo`)
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint URL
- `AZURE_OPENAI_MODEL`: Azure OpenAI model
- `AZURE_OPENAI_DEPLOYMENT`: Azure deployment name (optional, defaults to model name)
- `AZURE_OPENAI_API_VERSION`: Azure API version (optional, defaults to `2023-12-01`)
- `LOCAL_LLM_MODEL`: Local LLM model name (default: `mistral`)
- `LOCAL_LLM_ENDPOINT`: Local LLM endpoint (default: `http://localhost:11434`)
- `MOCK_LATENCY_MS`: Mock provider simulated latency (default: `100`)

## Providers

### OpenAI

```python
summarizer = SummarizerFactory.create_summarizer(
    provider="openai",
    api_key="sk-...",
    model="gpt-4"
)
```

### Azure OpenAI

```python
summarizer = SummarizerFactory.create_summarizer(
    provider="azure",
    api_key="your-azure-key",
    base_url="https://your-resource.openai.azure.com",
    model="gpt-4",
    deployment_name="gpt-4-deployment",  # Optional, defaults to model name
    api_version="2023-12-01"  # Optional, defaults to 2023-12-01
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
summarizer = SummarizerFactory.create_summarizer(
    provider="local",
    model="mistral",
    base_url="http://localhost:11434"
)
```

### Mock (for testing)

```python
summarizer = SummarizerFactory.create_summarizer(provider="mock")
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
- `SummarizerFactory`: Factory for creating summarizer instances
- `Thread`, `Summary`, `Citation`: Data models

## License

MIT License - see LICENSE file for details.
