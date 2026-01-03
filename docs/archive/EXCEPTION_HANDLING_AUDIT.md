<!-- SPDX-License-Identifier: MIT
    Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Exception Handling Audit - Implementation Summary

## Overview

This document summarizes the changes made to convert return-code-based error signaling to exception-based error handling across the CoPilot-For-Consensus codebase.

## Problem Statement

Several API surfaces in the project were using return codes (bool, None, tuples) to signal failure conditions. This led to:
- Silent failures when callers didn't check return values
- Difficult debugging when errors propagated undetected
- Inconsistent error handling patterns

## Solution

Refactored core services to use Python exceptions for error conditions, making failures explicit and impossible to ignore.

## Changes Made

### 1. Exception Classes Created

#### `ingestion/app/exceptions.py`
```python
class IngestionError(Exception):
    """Base exception for ingestion service errors."""

class SourceConfigurationError(IngestionError):
    """Invalid or missing source configuration."""

class FetchError(IngestionError):
    """Failed to fetch archives from source."""
    # Includes source_name and retry_count attributes

class ChecksumPersistenceError(IngestionError):
    """Failed to save checksum metadata."""

class ArchivePublishError(IngestionError):
    """Failed to publish archive events."""
    # Includes archive_id attribute
```

#### `parsing/app/exceptions.py`
```python
class ParsingError(Exception):
    """Base exception for parsing service errors."""

class MessageParsingError(ParsingError):
    """Failed to parse individual message."""
    # Includes message_index attribute

class MboxFileError(ParsingError):
    """Failed to open or read mbox file."""
    # Includes file_path attribute

class RequiredFieldMissingError(ParsingError):
    """Required field missing from message."""
    # Includes field_name and message_id attributes
```

### 2. Ingestion Service Refactored

#### Before:
```python
def ingest_archive(source) -> bool:
    # ...
    if not success:
        return False
    # ...
    return True

def ingest_all_enabled_sources() -> Dict[str, bool]:
    results = {}
    for source in sources:
        success = self.ingest_archive(source)
        results[source.name] = success
    return results
```

#### After:
```python
def ingest_archive(source) -> None:
    """Raises: SourceConfigurationError, FetchError, IngestionError"""
    # ...
    if not success:
        raise FetchError(error_msg, source_name=source.name, retry_count=retry_count)
    # Success - returns normally

def ingest_all_enabled_sources() -> Dict[str, Optional[Exception]]:
    """Returns dict mapping source name to None (success) or Exception (failure)."""
    results = {}
    for source in sources:
        try:
            self.ingest_archive(source)
            results[source.name] = None  # Success
        except Exception as e:
            results[source.name] = e  # Failure
    return results
```

### 3. Parsing Service Refactored

#### Before:
```python
def parse_mbox(path, archive_id) -> tuple[List[Dict], List[str]]:
    messages = []
    errors = []
    try:
        # parse...
    except Exception as e:
        errors.append(str(e))
    return messages, errors

def parse_message(message) -> Optional[Dict]:
    if not message_id:
        return None
    # ...
```

#### After:
```python
def parse_mbox(path, archive_id) -> List[Dict]:
    """Raises: MboxFileError, MessageParsingError"""
    messages = []
    try:
        # parse...
        if not messages and had_errors:
            raise MessageParsingError("No messages parsed")
    except Exception as e:
        raise MboxFileError(f"Failed to read {path}", file_path=path) from e
    return messages

def parse_message(message) -> Dict:
    """Raises: RequiredFieldMissingError"""
    if not message_id:
        raise RequiredFieldMissingError("Message-ID")
    # ...
```

### 4. Callers Updated

#### `ingestion/main.py`
```python
# Before
results = service.ingest_all_enabled_sources()
for source_name, success in results.items():
    status = "SUCCESS" if success else "FAILED"
    log.info(f"{source_name}: {status}")
successful = sum(1 for s in results.values() if s)

# After
results = service.ingest_all_enabled_sources()
for source_name, exception in results.items():
    if exception is None:
        log.info(f"{source_name}: SUCCESS")
    else:
        log.error(f"{source_name}: FAILED - {exception}")
successful = sum(1 for exc in results.values() if exc is None)
```

#### `parsing/app/service.py`
```python
# Before
parsed_messages, errors = self.parser.parse_mbox(file_path, archive_id)
if not parsed_messages:
    log.warning(f"No messages. Errors: {errors}")
    return

# After
try:
    parsed_messages = self.parser.parse_mbox(file_path, archive_id)
except Exception as parse_error:
    log.error(f"Parsing failed: {parse_error}")
    self._update_archive_status(archive_id, "failed", 0)
    raise
```

### 5. Tests Updated

Added new tests to validate exception behavior:
- `test_ingest_archive_raises_source_configuration_error()`
- `test_ingest_archive_raises_fetch_error()`
- `test_ingest_all_enabled_sources_returns_exceptions()`
- Updated existing tests to not expect return values

## Benefits

1. **Prevents Silent Failures**: Exceptions must be handled or propagated; they can't be silently ignored
2. **Better Debugging**: Stack traces and exception context make it easier to diagnose issues
3. **Type Safety**: Return type signatures are clearer (None vs Exception)
4. **Explicit Error Handling**: Callers must explicitly catch exceptions or document that they propagate
5. **Structured Error Information**: Custom exception classes carry contextual information (source_name, retry_count, etc.)

## Migration Guide

### For Service Developers

When adding new operations that may fail:
1. Define a custom exception class in the service's `exceptions.py` module
2. Raise the exception on failure with contextual information
3. Document exceptions in docstring with `Raises:` section
4. Never return False/None to indicate failure

Example:
```python
def process_data(self, data: Dict) -> ProcessedData:
    """Process input data.

    Args:
        data: Input data dictionary

    Returns:
        ProcessedData object

    Raises:
        ValidationError: If data validation fails
        ProcessingError: If processing fails
    """
    if not self._validate(data):
        raise ValidationError("Data missing required fields")

    try:
        result = self._process(data)
    except Exception as e:
        raise ProcessingError("Processing failed") from e

    return result
```

### For Callers

When calling operations that may raise exceptions:
1. Use try/except blocks to handle expected exceptions
2. Re-raise if you can't handle the exception
3. Log error details before re-raising for observability

Example:
```python
try:
    service.process_data(data)
except ValidationError as e:
    logger.warning(f"Validation failed: {e}")
    # Can handle this - return friendly error
    return {"error": "Invalid data"}
except ProcessingError as e:
    logger.error(f"Processing failed: {e}", exc_info=True)
    # Can't handle this - let it propagate
    raise
```

## Testing

All exception behavior should be tested:
```python
def test_raises_on_invalid_input():
    service = MyService()
    with pytest.raises(ValidationError, match="missing required fields"):
        service.process_data({"invalid": "data"})
```

## Next Steps

1. Apply same pattern to remaining services (orchestrator, reporting, error-reporting)
2. Add linting rules to detect unchecked return values (optional stretch goal)
3. Document exception handling patterns in CONTRIBUTING.md
4. Update API documentation to reflect exception-based contracts

## References

- PEP 3151: Reworking the OS and IO exception hierarchy
- Python Exceptions Best Practices: https://docs.python.org/3/tutorial/errors.html
- Issue: 🐛 Audit API Surfaces for Incorrect Use of Return Codes Instead of Exceptions
