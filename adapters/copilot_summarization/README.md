# copilot-summarization

LLM summarization adapter library with support for multiple providers (OpenAI, Azure OpenAI, local models).

## Overview

`copilot-summarization` provides a clean abstraction layer for LLM-based summarization, enabling seamless switching between different providers without changing application logic.

## Features

- **Multiple Provider Support**: OpenAI, Azure OpenAI, local models (Ollama, llama.cpp)
- **Factory Pattern**: Easy provider selection via environment variables
- **Mock Implementation**: Testing without external API calls
- **Extensible**: Simple interface for adding new providers

## Installation

```bash
pip install ./adapters/copilot_summarization
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

- `SUMMARIZER_PROVIDER`: Provider type (`openai`, `azure`, `local`, `mock`)
- `OPENAI_API_KEY`: OpenAI API key
- `OPENAI_MODEL`: OpenAI model to use (default: `gpt-3.5-turbo`)
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint URL
- `AZURE_OPENAI_MODEL`: Azure OpenAI model
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
    model="gpt-4"
)
```

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
- `OpenAISummarizer`: OpenAI/Azure OpenAI implementation
- `LocalLLMSummarizer`: Local LLM implementation (scaffold)
- `MockSummarizer`: Mock implementation for testing
- `SummarizerFactory`: Factory for creating summarizer instances
- `Thread`, `Summary`, `Citation`: Data models

## License

MIT License - see LICENSE file for details.
