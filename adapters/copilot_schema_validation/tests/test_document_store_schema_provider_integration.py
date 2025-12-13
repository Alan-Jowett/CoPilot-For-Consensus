# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration test for the document-store-backed schema provider - REMOVED.

DocumentStoreSchemaProvider has been removed to break the circular dependency 
between copilot_schema_validation and copilot_storage. The application now uses 
only FileSchemaProvider to load schemas from the file system.

This file is retained for reference but all tests have been removed.
"""

import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="DocumentStoreSchemaProvider has been removed")
def test_seeded_archive_ingested_schema_allows_valid_event():
    """Placeholder test - DocumentStoreSchemaProvider is no longer available."""
    pass

