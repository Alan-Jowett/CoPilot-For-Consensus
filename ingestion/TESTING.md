# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Testing Guide for Ingestion Service

## Overview

The ingestion service includes a comprehensive test suite with:
- **30+ Unit Tests**: Testing individual components in isolation
- **9 Integration Tests**: Testing complete end-to-end workflows

## Test Organization

```
tests/
├── test_config.py           # Configuration and source management tests
├── test_event_publisher.py  # Event publishing tests
├── test_archive_fetcher.py  # Archive fetching tests
├── test_service.py          # Service logic tests
├── test_integration.py      # End-to-end workflow tests
└── conftest.py              # Pytest configuration
```

## Setup

### Install Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install test dependencies
pip install pytest pytest-cov

# Or install everything
pip install -r requirements.txt pytest pytest-cov
```

### Verify Installation

```bash
pytest --version
python -m pytest --version
```

## Running Tests

### All Tests

```bash
pytest tests/ -v
```

### Unit Tests Only

```bash
pytest tests/test_config.py tests/test_event_publisher.py tests/test_archive_fetcher.py tests/test_service.py -v
```

### Integration Tests Only

```bash
pytest tests/test_integration.py -v
```

### Specific Test File

```bash
pytest tests/test_service.py -v
```

### Specific Test Class

```bash
pytest tests/test_service.py::TestIngestionService -v
```

### Specific Test Method

```bash
pytest tests/test_service.py::TestIngestionService::test_ingest_archive_success -v
```

### With Coverage Report

```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term
```

Coverage report will be generated in `htmlcov/index.html`

## Test Categories

### Configuration Tests (`test_config.py`)

Tests configuration loading and validation:

- **TestSourceConfig**
  - `test_source_config_from_dict_basic`: Basic source configuration
  - `test_source_config_from_dict_with_env_vars`: Environment variable expansion
  - `test_source_config_disabled`: Disabled source handling
  - `test_source_config_extra_fields`: Extra field handling

- **TestIngestionConfig**
  - `test_ingestion_config_from_env`: Loading from environment
  - `test_ingestion_config_defaults`: Default values
  - `test_ingestion_config_ensure_storage_path`: Storage path creation
  - `test_get_enabled_sources`: Source filtering

### Event Publisher Tests (`test_event_publisher.py`)

Tests event publishing:

- **TestNoopPublisher**
  - `test_noop_publisher_connect`: Connection
  - `test_noop_publisher_disconnect`: Disconnection
  - `test_noop_publisher_publish`: Single event publishing
  - `test_noop_publisher_multiple_publishes`: Multiple events

- **TestCreatePublisher**
  - `test_create_noop_publisher`: Factory creation
  - `test_create_publisher_invalid_type`: Error handling
  - `test_create_rabbitmq_publisher`: RabbitMQ creation

- **TestArchiveIngestedEvent**
  - `test_archive_ingested_event_defaults`: Default values
  - `test_archive_ingested_event_to_dict`: Serialization
  - `test_archive_ingested_event_json_serializable`: JSON compatibility

### Archive Fetcher Tests (`test_archive_fetcher.py`)

Tests archive fetching:

- **TestCalculateFileHash**
  - `test_calculate_file_hash_sha256`: Hash calculation
  - `test_calculate_file_hash_consistency`: Hash consistency

- **TestLocalFetcher**
  - `test_local_fetcher_copy_file`: Single file copying
  - `test_local_fetcher_copy_directory`: Directory copying
  - `test_local_fetcher_nonexistent_source`: Error handling

- **TestCreateFetcher**
  - `test_create_local_fetcher`: Factory creation
  - `test_create_fetcher_invalid_type`: Error handling

### Service Tests (`test_service.py`)

Tests ingestion service:

- **TestIngestionService**
  - `test_service_initialization`: Service setup
  - `test_add_and_check_checksum`: Checksum management
  - `test_save_and_load_checksums`: Checksum persistence
  - `test_ingest_archive_success`: Successful ingestion
  - `test_ingest_archive_duplicate`: Duplicate handling
  - `test_ingest_all_enabled_sources`: Multi-source ingestion
  - `test_ingestion_log_created`: Log file creation
  - `test_publish_success_event`: Event publishing
  - Additional tests for error handling and metadata

### Integration Tests (`test_integration.py`)

Tests complete workflows:

- **TestIngestionIntegration**
  - `test_end_to_end_ingestion`: Complete workflow
  - `test_ingestion_with_duplicates`: Duplicate handling
  - `test_ingestion_with_mixed_sources`: Enabled/disabled sources
  - `test_checksums_persist_across_instances`: Persistence
  - `test_ingestion_log_format`: Log format validation
  - `test_published_event_format`: Event format validation
  - `test_storage_directory_structure`: Directory structure

## Expected Test Output

Running all tests should produce output similar to:

```
============================= test session starts ==============================
collected 39 items

tests/test_config.py::TestSourceConfig::test_source_config_from_dict_basic PASSED
tests/test_config.py::TestSourceConfig::test_source_config_from_dict_with_env_vars PASSED
tests/test_config.py::TestSourceConfig::test_source_config_disabled PASSED
tests/test_config.py::TestSourceConfig::test_source_config_extra_fields PASSED
tests/test_config.py::TestIngestionConfig::test_ingestion_config_from_env PASSED
tests/test_config.py::TestIngestionConfig::test_ingestion_config_defaults PASSED
tests/test_config.py::TestIngestionConfig::test_ingestion_config_ensure_storage_path PASSED
tests/test_config.py::TestIngestionConfig::test_get_enabled_sources PASSED
tests/test_event_publisher.py::TestNoopPublisher::test_noop_publisher_connect PASSED
tests/test_event_publisher.py::TestNoopPublisher::test_noop_publisher_disconnect PASSED
tests/test_event_publisher.py::TestNoopPublisher::test_noop_publisher_publish PASSED
tests/test_event_publisher.py::TestNoopPublisher::test_noop_publisher_multiple_publishes PASSED
tests/test_event_publisher.py::TestCreatePublisher::test_create_noop_publisher PASSED
tests/test_event_publisher.py::TestCreatePublisher::test_create_publisher_invalid_type PASSED
tests/test_event_publisher.py::TestCreatePublisher::test_create_rabbitmq_publisher PASSED
tests/test_event_publisher.py::TestArchiveIngestedEvent::test_archive_ingested_event_defaults PASSED
tests/test_event_publisher.py::TestArchiveIngestedEvent::test_archive_ingested_event_to_dict PASSED
tests/test_event_publisher.py::TestArchiveIngestedEvent::test_archive_ingested_event_json_serializable PASSED
tests/test_archive_fetcher.py::TestCalculateFileHash::test_calculate_file_hash_sha256 PASSED
tests/test_archive_fetcher.py::TestCalculateFileHash::test_calculate_file_hash_consistency PASSED
tests/test_archive_fetcher.py::TestLocalFetcher::test_local_fetcher_copy_file PASSED
tests/test_archive_fetcher.py::TestLocalFetcher::test_local_fetcher_copy_directory PASSED
tests/test_archive_fetcher.py::TestLocalFetcher::test_local_fetcher_nonexistent_source PASSED
tests/test_archive_fetcher.py::TestCreateFetcher::test_create_local_fetcher PASSED
tests/test_archive_fetcher.py::TestCreateFetcher::test_create_fetcher_invalid_type PASSED
tests/test_service.py::TestIngestionService::test_service_initialization PASSED
tests/test_service.py::TestIngestionService::test_add_and_check_checksum PASSED
tests/test_service.py::TestIngestionService::test_save_and_load_checksums PASSED
tests/test_service.py::TestIngestionService::test_ingest_archive_success PASSED
tests/test_service.py::TestIngestionService::test_ingest_archive_duplicate PASSED
tests/test_service.py::TestIngestionService::test_ingest_all_enabled_sources PASSED
tests/test_service.py::TestIngestionService::test_ingestion_log_created PASSED
tests/test_service.py::TestIngestionService::test_publish_success_event PASSED
tests/test_integration.py::TestIngestionIntegration::test_end_to_end_ingestion PASSED
tests/test_integration.py::TestIngestionIntegration::test_ingestion_with_duplicates PASSED
tests/test_integration.py::TestIngestionIntegration::test_ingestion_with_mixed_sources PASSED
tests/test_integration.py::TestIngestionIntegration::test_checksums_persist_across_instances PASSED
tests/test_integration.py::TestIngestionIntegration::test_ingestion_log_format PASSED
tests/test_integration.py::TestIngestionIntegration::test_published_event_format PASSED
tests/test_integration.py::TestIngestionIntegration::test_storage_directory_structure PASSED

============================== 39 passed in 2.34s ===============================
```

## Coverage Analysis

Run tests with coverage to see what's tested:

```bash
pytest tests/ --cov=app --cov-report=html
```

Open `htmlcov/index.html` in a browser to see detailed coverage.

Expected coverage:
- `app/config.py`: ~95%
- `app/models.py`: ~100%
- `app/event_publisher.py`: ~80%
- `app/archive_fetcher.py`: ~75%
- `app/service.py`: ~85%

## Troubleshooting

### Import Errors

If you get "Import could not be resolved" errors:

```bash
# Make sure you're in the ingestion directory
cd ingestion

# Verify PYTHONPATH includes current directory
python -c "import sys; print(sys.path)"

# Run pytest from ingestion directory
pytest tests/ -v
```

### Dependency Issues

If you get missing dependency errors:

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Verify installation
python -c "import pika; import yaml; print('Dependencies OK')"
```

### Test Failures

If tests fail, check:

1. **Working Directory**: Make sure you're in the `ingestion/` directory
2. **Python Version**: Requires Python 3.8+
3. **Dependencies**: Run `pip install -r requirements.txt pytest`
4. **File Permissions**: Ensure test files are readable
5. **Temporary Directories**: Tests use `tempfile` - ensure `/tmp` or equivalent is writable

### Verbose Output

For detailed debugging:

```bash
# Very verbose output
pytest tests/ -vv

# Show print statements
pytest tests/ -v -s

# Show local variables on failure
pytest tests/ -v -l

# Drop into debugger on failure
pytest tests/ -v --pdb
```

## Continuous Integration

For CI/CD pipelines:

```bash
# Exit with error if any test fails
pytest tests/ --tb=short --strict-markers

# Generate JUnit XML report
pytest tests/ --junitxml=test-results.xml

# Generate coverage report
pytest tests/ --cov=app --cov-report=xml --cov-report=term

# Combine all
pytest tests/ \
  --junitxml=test-results.xml \
  --cov=app \
  --cov-report=xml \
  --cov-report=html \
  --tb=short
```

## Performance

Test execution is fast (< 5 seconds total):
- Unit tests use mocks and fixtures
- Tests use temporary directories (no I/O overhead)
- No external service dependencies for tests
- Can run in parallel: `pytest -n auto` (requires pytest-xdist)

## Extending Tests

To add new tests:

1. Create test file in `tests/` with `test_*.py` pattern
2. Import fixtures from `conftest.py`
3. Use `@pytest.fixture` for reusable setup
4. Run `pytest tests/ -v` to discover and run new tests

Example:

```python
import pytest
from app.config import SourceConfig

def test_new_functionality():
    """Test description."""
    source = SourceConfig(
        name="test",
        source_type="local",
        url="/path",
    )
    assert source.name == "test"
```

## Documentation

- **IMPLEMENTATION.md**: Detailed implementation guide
- **IMPLEMENTATION_SUMMARY.md**: High-level overview
- **README.md**: Service overview
- **Source code comments**: Inline documentation
