# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration test for MongoSchemaProvider using seeded MongoDB schemas.

Requires a running MongoDB seeded by infra/init (db-init container). The test
skips automatically if MongoDB is unavailable.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest

from copilot_events.mongo_schema_provider import MongoSchemaProvider
from copilot_events.schema_validator import validate_json


DEFAULT_USERNAME = os.getenv("MONGO_USERNAME", "admin")
DEFAULT_PASSWORD = os.getenv("MONGO_PASSWORD", "PLEASE_CHANGE_ME")
DEFAULT_URI = os.getenv(
    "MONGO_URI",
    f"mongodb://{DEFAULT_USERNAME}:{DEFAULT_PASSWORD}@localhost:27017/admin?authSource=admin",
)
DEFAULT_DB = os.getenv("MONGO_DB", "copilot")
DEFAULT_COLLECTION = os.getenv("MONGO_COLLECTION", "event_schemas")


def _mongo_available(uri: str) -> bool:
    try:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


@pytest.mark.integration
def test_seeded_archive_ingested_schema_allows_valid_event():
    if not _mongo_available(DEFAULT_URI):
        pytest.skip("MongoDB not available; ensure db-init container has seeded schemas")

    provider = MongoSchemaProvider(
        mongo_uri=DEFAULT_URI,
        database_name=DEFAULT_DB,
        collection_name=DEFAULT_COLLECTION,
    )

    schema = provider.get_schema("ArchiveIngested")
    if schema is None:
        pytest.skip("ArchiveIngested schema not found in MongoDB; seed may not have run")

    event = {
        "event_type": "ArchiveIngested",
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "data": {
            "archive_id": str(uuid.uuid4()),
            "source_name": "source-A",
            "source_type": "http",
            "source_url": "https://example.com/archive.zip",
            "file_path": "/data/archive.zip",
            "file_size_bytes": 1234,
            "file_hash_sha256": "deadbeef" * 4,
            "ingestion_started_at": datetime.now(timezone.utc).isoformat(),
            "ingestion_completed_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    is_valid, errors = validate_json(event, schema, schema_provider=provider)
    provider.close()

    assert is_valid, f"Seeded schema rejected valid event: {errors}"