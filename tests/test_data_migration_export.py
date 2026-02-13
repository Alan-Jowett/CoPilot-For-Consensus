# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for data-migration-export.py."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Load the export module dynamically (filename has hyphens)
_spec = importlib.util.spec_from_file_location(
    "data_migration_export",
    Path(__file__).resolve().parent.parent / "scripts" / "data-migration-export.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_redact_uri = _mod._redact_uri
DATABASE_COLLECTIONS = _mod.DATABASE_COLLECTIONS
export_cosmos = _mod.export_cosmos
export_mongodb = _mod.export_mongodb


class TestRedactUri:
    """Credential redaction for manifest.json."""

    def test_redacts_user_password(self):
        uri = "mongodb://admin:s3cret@host:27017/?authSource=admin"
        assert _redact_uri(uri) == "mongodb://<redacted>@host:27017/?authSource=admin"

    def test_redacts_complex_password(self):
        uri = "mongodb://user:p%40ss%3Aw0rd@host:10255/?ssl=true"
        assert _redact_uri(uri) == "mongodb://<redacted>@host:10255/?ssl=true"

    def test_no_credentials_unchanged(self):
        uri = "mongodb://host:27017/"
        assert _redact_uri(uri) == "mongodb://host:27017/"

    def test_redacts_only_credentials(self):
        uri = "mongodb://user:pass@host:27017/db?opt=1"
        result = _redact_uri(uri)
        assert "user" not in result
        assert "pass" not in result
        assert "host:27017/db?opt=1" in result


class TestDatabaseCollections:
    """Verify the export collection mapping is complete."""

    def test_copilot_includes_reports(self):
        assert "reports" in DATABASE_COLLECTIONS["copilot"]

    def test_auth_includes_user_roles(self):
        assert "user_roles" in DATABASE_COLLECTIONS["auth"]

    def test_all_expected_collections(self):
        expected = {"sources", "archives", "messages", "threads",
                    "chunks", "summaries", "reports"}
        assert set(DATABASE_COLLECTIONS["copilot"]) == expected


class TestExportCosmos:
    """Cosmos DB export with mocked SDK."""

    def test_exports_documents_as_ndjson(self, tmp_path):
        """Verify streaming NDJSON write from Cosmos query."""
        mock_container = MagicMock()
        mock_container.query_items.return_value = iter([
            {"id": "1", "data": "a", "_rid": "x", "_self": "y",
             "_etag": "z", "_attachments": "", "_ts": 123},
            {"id": "2", "data": "b", "_rid": "x2", "_self": "y2",
             "_etag": "z2", "_attachments": "", "_ts": 456},
        ])

        mock_db = MagicMock()
        mock_db.get_container_client.return_value = mock_container

        mock_client = MagicMock()
        mock_client.get_database_client.return_value = mock_db

        out_dir = tmp_path / "export"
        (out_dir / "testdb").mkdir(parents=True)

        with patch("azure.cosmos.CosmosClient", return_value=mock_client):
            counts = export_cosmos(
                "https://test.documents.azure.com:443/",
                "fakekey", False,
                {"testdb": ["coll1"]}, out_dir,
            )

        assert counts["testdb.coll1"] == 2
        out_file = out_dir / "testdb" / "coll1.json"
        assert out_file.exists()

        lines = out_file.read_text().strip().split("\n")
        assert len(lines) == 2
        doc1 = json.loads(lines[0])
        assert doc1 == {"id": "1", "data": "a"}
        assert "_rid" not in doc1

    def test_handles_missing_database(self, tmp_path):
        """Verify graceful handling when database doesn't exist."""
        mock_client = MagicMock()
        mock_client.get_database_client.side_effect = Exception("Not found")

        out_dir = tmp_path / "export"
        (out_dir / "baddb").mkdir(parents=True)

        with patch("azure.cosmos.CosmosClient", return_value=mock_client):
            counts = export_cosmos(
                "https://test.documents.azure.com:443/",
                "fakekey", False,
                {"baddb": ["coll"]}, out_dir,
            )

        assert counts == {}


class TestExportMongoDB:
    """MongoDB export with mocked pymongo."""

    def test_exports_documents_as_ndjson(self, tmp_path):
        """Verify streaming NDJSON write from MongoDB cursor."""
        from bson import ObjectId

        mock_coll = MagicMock()
        mock_coll.find.return_value = iter([
            {"_id": ObjectId("507f1f77bcf86cd799439011"), "data": "a"},
            {"_id": "string-id", "data": "b"},
        ])

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)

        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        out_dir = tmp_path / "export"
        (out_dir / "testdb").mkdir(parents=True)

        with patch("pymongo.MongoClient", return_value=mock_client):
            counts = export_mongodb(
                "mongodb://localhost:27017/",
                {"testdb": ["coll1"]}, out_dir,
            )

        assert counts["testdb.coll1"] == 2
        out_file = out_dir / "testdb" / "coll1.json"
        lines = out_file.read_text().strip().split("\n")
        assert len(lines) == 2
        # ObjectId should be serialized as string
        doc1 = json.loads(lines[0])
        assert doc1["_id"] == "507f1f77bcf86cd799439011"

    def test_handles_collection_error(self, tmp_path):
        """Verify error handling for collection access failures."""
        mock_coll = MagicMock()
        mock_coll.find.side_effect = Exception("Connection refused")

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)

        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        out_dir = tmp_path / "export"
        (out_dir / "testdb").mkdir(parents=True)

        with patch("pymongo.MongoClient", return_value=mock_client):
            counts = export_mongodb(
                "mongodb://localhost:27017/",
                {"testdb": ["coll1"]}, out_dir,
            )

        assert counts["testdb.coll1"] == -1
