<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Draft Diff Provider Abstraction Layer

This package provides an abstraction layer for fetching and representing draft diffs from multiple sources (e.g., Datatracker, GitHub, local files) and in multiple formats (e.g., HTML, Markdown, plain text).

## Features

- **Abstraction Layer**: Common interface for fetching draft diffs from different sources
- **Multiple Providers**: Support for Datatracker (default), mock (for testing), and extensible for future providers
- **Multiple Formats**: Support for HTML, Markdown, and plain text diffs
- **Factory Pattern**: Easy configuration and provider selection based on environment or config
- **Type Safe**: Strongly typed with Python dataclasses

## Usage

### Basic Usage

```python
from draft_diff import create_diff_provider

# Create a provider (uses environment variables by default)
provider = create_diff_provider()

# Fetch a diff between two versions
diff = provider.getdiff(
    draft_name="draft-ietf-quic-transport",
    version_a="01",
    version_b="02"
)

print(f"Draft: {diff.draft_name}")
print(f"Format: {diff.format}")
print(f"Content:\n{diff.content}")
```

### Using Specific Providers

```python
from draft_diff import create_diff_provider

# Use mock provider for testing
provider = create_diff_provider("mock", {"default_format": "html"})
diff = provider.getdiff("draft-test", "00", "01")

# Use datatracker provider (stub - not yet fully implemented)
provider = create_diff_provider("datatracker", {
    "base_url": "https://datatracker.ietf.org",
    "format": "html"
})
```

### Using Environment Variables

Configure the provider using environment variables:

```bash
# Set provider type (default: datatracker)
export DRAFT_DIFF_PROVIDER=mock

# Set datatracker-specific config
export DRAFT_DIFF_BASE_URL=https://datatracker.ietf.org
export DRAFT_DIFF_FORMAT=html
```

Then in your code:

```python
from draft_diff import create_diff_provider

# Automatically uses environment configuration
provider = create_diff_provider()
diff = provider.getdiff("draft-ietf-quic-transport", "01", "02")
```

### Using the Factory Directly

```python
from draft_diff import DiffProviderFactory

# Create provider
provider = DiffProviderFactory.create("mock", {"default_format": "markdown"})

# Create from environment
provider = DiffProviderFactory.create_from_env()
```

### Extending with Custom Providers

You can register custom provider implementations:

```python
from draft_diff import DiffProviderFactory, DraftDiffProvider, DraftDiff

class CustomProvider(DraftDiffProvider):
    def getdiff(self, draft_name: str, version_a: str, version_b: str) -> DraftDiff:
        # Custom implementation
        return DraftDiff(
            draft_name=draft_name,
            version_a=version_a,
            version_b=version_b,
            format="text",
            content="Custom diff content",
            source="custom"
        )

# Register the provider
DiffProviderFactory.register_provider("custom", CustomProvider)

# Use it
provider = DiffProviderFactory.create("custom")
diff = provider.getdiff("draft-test", "01", "02")
```

## Available Providers

### MockDiffProvider

For testing purposes. Generates synthetic diff data.

```python
from draft_diff import MockDiffProvider, DraftDiff

# Create with auto-generation
provider = MockDiffProvider(default_format="html")
diff = provider.getdiff("draft-test", "01", "02")

# Add predefined mocks
predefined = DraftDiff(
    draft_name="draft-custom",
    version_a="01",
    version_b="02",
    format="text",
    content="Predefined content",
    source="mock"
)
provider.add_mock_diff("draft-custom", "01", "02", predefined)
```

### DatatrackerDiffProvider

For fetching diffs from IETF Datatracker (stub implementation).

```python
from draft_diff import DatatrackerDiffProvider

provider = DatatrackerDiffProvider(
    base_url="https://datatracker.ietf.org",
    format="html"
)

# Note: Full implementation requires HTTP client integration
# Currently raises NotImplementedError
```

## Data Model

### DraftDiff

Represents a diff between two versions of a draft:

```python
@dataclass
class DraftDiff:
    draft_name: str          # e.g., "draft-ietf-quic-transport"
    version_a: str           # e.g., "01"
    version_b: str           # e.g., "02"
    format: str              # e.g., "html", "markdown", "text"
    content: str             # The diff content
    source: str              # e.g., "datatracker", "github", "mock"
    url: Optional[str]       # Optional URL to view the diff
    metadata: Optional[dict] # Optional additional metadata
```

## Integration with Services

### In Summarization Service

```python
from draft_diff import create_diff_provider

# In your service initialization
diff_provider = create_diff_provider()

# When processing drafts
def process_draft_changes(draft_name: str, old_version: str, new_version: str):
    diff = diff_provider.getdiff(draft_name, old_version, new_version)
    
    # Process the diff content
    summary = summarize_diff(diff.content)
    
    return {
        "draft": diff.draft_name,
        "versions": f"{diff.version_a} -> {diff.version_b}",
        "summary": summary,
        "source": diff.source
    }
```

## Testing

Run the tests:

```bash
cd adapters
python -m pytest tests/test_draft_diff/ -v
```

## Future Enhancements

- **GitHubDiffProvider**: Fetch diffs from GitHub repositories
- **LocalDiffProvider**: Load diffs from local files
- **HTTP Client Integration**: Complete DatatrackerDiffProvider implementation
- **Caching**: Add diff caching to reduce API calls
- **Async Support**: Add async versions of diff fetching methods
