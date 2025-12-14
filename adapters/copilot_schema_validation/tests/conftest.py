# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration and shared fixtures for schema validation tests."""

import pytest
from pathlib import Path
from copilot_schema_validation import FileSchemaProvider


@pytest.fixture(scope="session")
def document_schema_provider():
    """Get schema provider for document schemas (shared across all tests)."""
    schema_dir = Path(__file__).parent.parent.parent.parent / "documents" / "schemas" / "documents"
    return FileSchemaProvider(schema_dir=schema_dir)
