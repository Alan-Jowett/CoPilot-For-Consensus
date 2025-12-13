<!-- SPDX-License-Identifier: MIT
    Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Archive Fetcher Adapter

A shared library for fetching archives from various sources in the Copilot-for-Consensus system.

## Overview

The Archive Fetcher Adapter provides a unified interface for fetching archives from multiple source types:

- **rsync**: Synchronize files via rsync protocol
- **HTTP**: Download files via HTTP/HTTPS
- **Local**: Copy files from local filesystem
- **IMAP**: Fetch emails from IMAP servers

## Installation

### Basic Installation

```bash
pip install copilot-archive-fetcher
```

### With Optional Dependencies

For HTTP support:
```bash
pip install copilot-archive-fetcher[http]
```

For IMAP support:
```bash
pip install copilot-archive-fetcher[imap]
```

For development:
```bash
pip install copilot-archive-fetcher[dev]
```

## Usage

### Basic Example

```python
from copilot_archive_fetcher import create_fetcher, SourceConfig

# Create a source configuration
config = SourceConfig(
    name="my-archive",
    source_type="http",
    url="https://example.com/archive.zip"
)

# Create a fetcher using the factory
fetcher = create_fetcher(config)

# Fetch the archive
success, files, error = fetcher.fetch("/path/to/output")

if success:
    print(f"Fetched {len(files)} files")
else:
    print(f"Error: {error}")
```

### Rsync Source

```python
config = SourceConfig(
    name="rsync-archive",
    source_type="rsync",
    url="rsync://example.com/archive/"
)
```

### Local Source

```python
config = SourceConfig(
    name="local-archive",
    source_type="local",
    url="/path/to/local/directory"
)
```

### IMAP Source

```python
config = SourceConfig(
    name="email-archive",
    source_type="imap",
    url="imap.example.com",
    port=993,
    username="user@example.com",
    password="secret",
    folder="INBOX"
)
```

### File Hashing

```python
from copilot_archive_fetcher import calculate_file_hash

# Calculate SHA256 hash
hash_value = calculate_file_hash("/path/to/file")
print(f"SHA256: {hash_value}")

# Calculate with different algorithm
md5_hash = calculate_file_hash("/path/to/file", algorithm="md5")
```

## Architecture

The adapter uses the factory pattern with an abstract base class:

```
ArchiveFetcher (abstract base)
├── RsyncFetcher
├── HTTPFetcher
├── LocalFetcher
└── IMAPFetcher
```

Each fetcher implements the `fetch()` method which returns a tuple of:
- `success` (bool): Whether the operation succeeded
- `files` (list): List of file paths if successful, None otherwise
- `error` (str): Error message if failed, None otherwise

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=copilot_archive_fetcher
```

Run specific tests:

```bash
pytest tests/test_local_fetcher.py
```

## Error Handling

The adapter provides specific exception types:

- `ArchiveFetcherError`: Base exception class
- `UnsupportedSourceTypeError`: Unknown source type
- `FetchError`: Generic fetch operation error
- `ConfigurationError`: Invalid configuration

```python
from copilot_archive_fetcher import create_fetcher, UnsupportedSourceTypeError

try:
    fetcher = create_fetcher(config)
except UnsupportedSourceTypeError as e:
    print(f"Unsupported source: {e}")
```

## Integration with Ingestion Service

This module is designed to be integrated with the Copilot-for-Consensus ingestion service. It can be imported and used as:

```python
from copilot_archive_fetcher import create_fetcher, SourceConfig

# In ingestion pipeline
config = load_source_config()  # From your config
fetcher = create_fetcher(config)
success, files, error = fetcher.fetch(output_dir)
```

## Dependencies

### Required
- Python >= 3.10

### Optional
- `requests` >= 2.28.0 (for HTTP sources)
- `imapclient` >= 2.3.0 (for IMAP sources)

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please ensure:
1. All tests pass
2. Code follows the project style guidelines
3. New features include tests
4. Documentation is updated
