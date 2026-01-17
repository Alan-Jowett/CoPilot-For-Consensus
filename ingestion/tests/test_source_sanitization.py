# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Regression tests for source document sanitization.

These tests ensure ingestion can consume source documents that include
Cosmos DB metadata fields (e.g., _etag/_rid/_ts) without failing.
"""

from app.service import _source_from_mapping


def test_source_from_mapping_ignores_cosmos_metadata_fields():
    source = {
        "name": "test-source",
        "source_type": "local",
        "url": "/data/raw_archives/uploads/test-archive.mbox",
        "enabled": True,
        # Cosmos/system fields that must be ignored
        "_attachments": "attachments/",
        "_etag": "00000000-0000-0000-0000-000000000000",
        "_rid": "abc123==",
        "_self": "dbs/abc/colls/def/docs/ghi/",
        "_ts": 1700000000,
        # App/document-store fields sometimes present
        "collection": "sources",
        "id": "some-id",
    }

    cfg = _source_from_mapping(source)

    assert cfg.name == "test-source"
    assert cfg.source_type == "local"
    assert cfg.url == "/data/raw_archives/uploads/test-archive.mbox"
    assert cfg.enabled is True
