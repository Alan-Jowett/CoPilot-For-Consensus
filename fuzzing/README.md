<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Fuzzing Infrastructure

This directory contains the fuzzing infrastructure for Copilot-for-Consensus, used for security testing and finding edge cases through automated input generation.

## Overview

Fuzzing is an automated testing technique that provides invalid, unexpected, or random data as inputs to a program to find bugs, crashes, and security vulnerabilities. This project uses three complementary fuzzing approaches:

### Tools Used

1. **Atheris** - Coverage-guided fuzzing for Python
   - Native code fuzzing using libFuzzer
   - Best for: Finding crashes, memory issues, and unexpected behavior
   - Example use cases: Parsing functions, data validators, serialization/deserialization

2. **Hypothesis** - Property-based testing framework
   - Generates test cases based on properties and invariants
   - Best for: Testing business logic, API contracts, data transformations
   - Example use cases: Ensuring idempotency, validating data pipelines, testing forward progress guarantees

3. **Schemathesis** - API schema-based fuzzing
   - Generates test cases from OpenAPI specifications
   - Best for: REST API endpoint testing, input validation
   - Example use cases: Testing ingestion API, reporting API, auth endpoints

## Directory Structure

```
fuzzing/
├── README.md           # This file
├── __init__.py
├── corpus/             # Seed inputs for fuzzing
│   ├── filenames/      # Malicious filename samples
│   └── mbox/           # Mbox file samples
└── tests/
    ├── __init__.py
    ├── test_atheris_example.py               # Example atheris fuzzing test
    ├── test_hypothesis_example.py            # Example hypothesis property-based test
    ├── test_jwt_fuzzing.py                   # JWT authentication fuzzing (auth service)
    ├── test_schemathesis_example.py          # Example schemathesis API fuzzing test
    ├── test_ingestion_upload_fuzzing.py      # Atheris fuzzing for ingestion uploads
    └── test_ingestion_upload_properties.py   # Hypothesis tests for upload security
```

## Running Fuzzing Tests

### Locally

```bash
# Install fuzzing dependencies
pip install -r requirements-dev.txt

# Run all fuzzing tests (with timeout to prevent infinite loops)
cd fuzzing
pytest tests/ -v --timeout=300

# Run specific fuzzing tool tests
pytest tests/test_hypothesis_example.py -v
pytest tests/test_schemathesis_example.py -v

# Run ingestion upload security tests
pytest tests/test_ingestion_upload_properties.py -v

# Run atheris fuzzing tests (requires special handling)
# Note: Atheris may not be available on all platforms (requires compilation)
python tests/test_atheris_example.py -atheris_runs=1000

# Run ingestion upload atheris fuzzing with different targets
python tests/test_ingestion_upload_fuzzing.py -target=sanitization -atheris_runs=10000
python tests/test_ingestion_upload_fuzzing.py -target=extension -atheris_runs=10000
python tests/test_ingestion_upload_fuzzing.py -target=mbox -atheris_runs=5000
```

### In CI

Fuzzing tests run automatically in the CI pipeline via the `.github/workflows/fuzzing.yml` workflow. The workflow:

- Runs on pushes to `main` and pull requests when fuzzing-related files are modified (for example: `fuzzing/**`, `requirements-dev.txt`, or the workflow file itself)
- Also runs on a scheduled weekly job
- Has a conservative timeout to prevent resource exhaustion
- Reports failures as test results
- Runs in parallel with other validation checks

## Writing Fuzzing Tests

### Atheris Example

```python
import atheris
import sys

def test_function(data):
    """Function to fuzz - should handle arbitrary input gracefully."""
    try:
        # Your parsing/validation logic here
        result = parse_data(data)
    except ValueError:
        # Expected exceptions should be caught
        pass

def main():
    atheris.Setup(sys.argv, test_function)
    atheris.Fuzz()

if __name__ == "__main__":
    main()
```

### Hypothesis Example

```python
from hypothesis import given, strategies as st
import pytest

@given(st.text())
def test_idempotency(input_data):
    """Test that processing is idempotent."""
    result1 = process(input_data)
    result2 = process(input_data)
    assert result1 == result2
```

### Schemathesis Example

```python
from schemathesis.openapi import from_uri

schema = from_uri("http://localhost:8000/openapi.json")

@schema.parametrize()
def test_api(case):
    """Test API endpoint against OpenAPI spec."""
    response = case.call()
    case.validate_response(response)
```

## Best Practices

1. **Set Timeouts**: Always use pytest timeout (`--timeout=300`) to prevent infinite loops
2. **Isolate Tests**: Each fuzzing test should be independent and not affect others
3. **Handle Expected Exceptions**: Catch and ignore exceptions that are part of normal validation
4. **Focus on Critical Paths**: Prioritize fuzzing for:
   - Input parsers (email, mailbox files)
   - API endpoints (especially public-facing ones)
   - Data validators and transformers
   - Authentication and authorization logic

5. **Monitor Resources**: Fuzzing can be resource-intensive; set appropriate limits
6. **Review Findings**: Not all fuzzing failures are bugs - analyze each finding carefully

## Coverage Goals

- **Parsers**: 100% of email parsing and mailbox handling code
- **APIs**: All public REST endpoints via schemathesis
- **Validators**: All input validation and sanitization functions
- **Data Pipelines**: Critical data transformation logic
- **Authentication**: JWT token parsing, signature validation, and claims extraction
- **Auth Service**: OIDC callback flow, state parameter validation, session management

## Fuzzing Tests

### JWT Authentication Fuzzing (`test_jwt_fuzzing.py`)

Comprehensive property-based fuzzing tests for JWT authentication in the auth service:

- **Header Parsing**: Tests malformed headers, algorithm confusion ("none", HS256 vs RS256), invalid key IDs
- **Signature Validation**: Tests signature bypass attempts, tampering, and mismatched keys
- **Claims Extraction**: Tests malformed claims, type confusion, missing required claims, injection attempts
- **Timing Validation**: Tests expired tokens, nbf edge cases, and clock skew boundary conditions
- **Algorithm Confusion**: Tests RS256 vs HS256 confusion attacks
- **Payload Size**: Tests DoS via large payloads

Priority: **P0** (Authentication bypass, privilege escalation risks)

### Auth Service OIDC Callback Fuzzing (`test_auth_callback_fuzzing.py`)

Comprehensive fuzzing for the auth service OIDC callback flow:

- **Property-based tests** (Hypothesis):
  - Callback endpoint never crashes with arbitrary input
  - Always returns valid JSON responses
  - Invalid states are rejected (CSRF protection)
  - Bad authorization codes are rejected
  - No injection vulnerabilities in parameters

- **API schema tests** (Schemathesis):
  - OpenAPI spec compliance for `/callback` endpoint
  - Error handling for malformed requests
  - Parameter validation edge cases

- **Security-focused edge cases**:
  - Missing/empty parameters
  - Very long parameters (DoS protection)
  - Unicode and special characters
  - SQL injection, XSS, command injection attempts
  - Path traversal attempts
  - CSRF via state manipulation
  - Session expiry handling
  - Replay attack prevention (single-use states)

Priority: **P0** (CSRF attacks, open redirect, injection vulnerabilities)

### Current Coverage

#### Ingestion Upload Security (P0)
- ✅ **Filename sanitization** - Atheris + Hypothesis testing for path traversal, null bytes, encoding attacks
- ✅ **Extension validation** - Hypothesis property-based tests for bypass attempts
- ✅ **Mbox parsing** - Atheris fuzzing for crash detection and malformed data handling
- ✅ **Size limits** - Property tests for boundary conditions

**Security Focus**: Protects against:
- Path traversal attacks (../../../etc/passwd)
- Null byte injection (filename\x00.exe)
- Extension confusion (.mbox.exe)
- Memory exhaustion from malformed mbox files
- Unicode/homograph attacks

**Test Files**:
- `tests/test_ingestion_upload_fuzzing.py` - Atheris coverage-guided fuzzing
- `tests/test_ingestion_upload_properties.py` - Hypothesis property-based tests
- `corpus/` - Seed inputs for fuzzing

## Contributing

When adding new features that handle external input:

1. Add corresponding fuzzing tests
2. Ensure tests run within timeout limits
3. Document any expected exceptions
4. Update this README if introducing new fuzzing patterns

## Security

Fuzzing is a critical part of our security strategy:

- Helps find input validation bugs before they reach production
- Tests edge cases that manual testing might miss
- Validates forward progress guarantees under stress
- Ensures APIs handle malformed requests gracefully

Report any security issues found through fuzzing according to [SECURITY.md](../SECURITY.md).
