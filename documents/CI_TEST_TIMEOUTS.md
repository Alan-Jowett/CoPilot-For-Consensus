# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# CI Test Timeout Configuration

## Overview

This document describes the timeout configuration for tests running in GitHub Actions CI to prevent jobs from hanging indefinitely.

## Problem

CI jobs for services were occasionally hanging for extended periods (5+ hours) during the test phase, causing:
- Blocked PR merges that require CI to pass
- Wasted GitHub Actions minutes
- Delayed development workflow

## Solution

We implemented a multi-layered timeout strategy:

### 1. Per-Test Timeout (pytest-timeout)

Each individual test has a maximum execution time of **300 seconds (5 minutes)**.

**Configuration:**
- File: `<service>/pytest.ini`
- Setting: `timeout = 300`
- Plugin: `pytest-timeout`

**Example:**
```ini
[pytest]
timeout = 300
```

This timeout applies to all tests unless overridden with explicit markers.

### 2. Job-Level Timeout (GitHub Actions)

Each test job has a maximum execution time of **30 minutes**.

**Configuration:**
- Files: 
  - `.github/workflows/service-reusable-unit-test-ci.yml` (for services)
  - `.github/workflows/adapter-reusable-unit-test-ci.yml` (for adapters)
- Setting: `timeout-minutes: 30`

**Example:**
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 30
```

This serves as a safety net in case pytest-timeout doesn't catch everything (e.g., process hangs outside test execution).

## Timeout Values

| Level | Timeout | Rationale |
|-------|---------|-----------|
| Per-Test | 300 seconds (5 minutes) | Most tests complete in seconds; 5 minutes is generous for integration tests |
| Job-Level | 30 minutes | Allows for ~20-25 minutes of actual test execution plus setup/teardown overhead |

## Overriding Timeouts

If a specific test legitimately needs more time, use the `@pytest.mark.timeout()` decorator:

```python
import pytest

@pytest.mark.timeout(600)  # 10 minutes
def test_long_running_operation():
    # This test can run for up to 10 minutes
    pass

@pytest.mark.timeout(0)  # Disable timeout
def test_no_timeout():
    # This test has no timeout limit
    pass
```

## Affected Services and Adapters

All services have timeout configuration:
- chunking
- embedding
- ingestion
- orchestrator
- parsing
- reporting
- summarization

All adapters have timeout configuration:
- copilot_archive_fetcher
- copilot_auth
- copilot_chunking
- copilot_config
- copilot_consensus
- copilot_draft_diff
- copilot_embedding
- copilot_events
- copilot_logging
- copilot_metrics
- copilot_reporting
- copilot_schema_validation
- copilot_storage
- copilot_summarization
- copilot_vectorstore

## Testing

To verify timeout configuration works:

```bash
# Create a test that sleeps longer than timeout
cat > /tmp/test_timeout.py << 'EOF'
import time

def test_should_timeout():
    time.sleep(400)  # Longer than 300s timeout
    assert True
EOF

# Run test (should fail with timeout)
cd <service>
pytest /tmp/test_timeout.py -v
```

Expected output:
```
FAILED test_timeout.py::test_should_timeout - Failed: Timeout (>300.0s)
```

## Troubleshooting

### Test times out but shouldn't

1. Check if test is genuinely slow or has a deadlock/infinite loop
2. Consider optimizing the test or splitting into smaller tests
3. If legitimately slow, add explicit timeout marker: `@pytest.mark.timeout(600)`

### Job times out but tests pass

- Increase `timeout-minutes` in workflow configuration
- Check for slow setup/teardown operations
- Review dependency installation time

### Timeout doesn't trigger

- Verify `pytest-timeout` is installed: `pip list | grep pytest-timeout`
- Check pytest.ini is in the correct location
- Ensure pytest picks up the configuration: `pytest --version -c pytest.ini`

## References

- pytest-timeout documentation: https://github.com/pytest-dev/pytest-timeout
- GitHub Actions timeout: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idtimeout-minutes
- Issue: CI jobs hanging for hours in reporting and chunking services
