# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration and shared fixtures for schema validation tests."""

from pathlib import Path

import pytest
from copilot_schema_validation import FileSchemaProvider


@pytest.fixture(scope="session")
def document_schema_provider():
    """Get schema provider for document schemas (shared across all tests)."""
    schema_dir = Path(__file__).parent.parent.parent.parent / "docs" / "schemas" / "documents" / "v1"
    return FileSchemaProvider(schema_dir=schema_dir)
