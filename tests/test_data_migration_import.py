# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for data-migration-import.py."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Load the import module dynamically (filename has hyphens)
_spec = importlib.util.spec_from_file_location(
    "data_migration_import",
    Path(__file__).resolve().parent.parent / "scripts" / "data-migration-import.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

iter_ndjson = _mod.iter_ndjson
count_ndjson_lines = _mod.count_ndjson_lines
COSMOS_PARTITION_KEYS = _mod.COSMOS_PARTITION_KEYS
import_mongodb = _mod.import_mongodb


class TestIterNdjson:
    """NDJSON streaming reader."""

    def test_reads_valid_ndjson(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"id":"1"}\n{"id":"2"}\n{"id":"3"}\n')
        items = list(iter_ndjson(f))
        assert len(items) == 3
        assert items[0]["id"] == "1"
        assert items[2]["id"] == "3"

    def test_skips_blank_lines(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"id":"1"}\n\n\n{"id":"2"}\n')
        items = list(iter_ndjson(f))
        assert len(items) == 2

    def test_empty_file(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text("")
        items = list(iter_ndjson(f))
        assert items == []

    def test_invalid_json_raises(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"id":"1"}\nnot-json\n')
        items_iter = iter_ndjson(f)
        next(items_iter)  # first line OK
        with pytest.raises(json.JSONDecodeError):
            next(items_iter)


class TestCountNdjsonLines:
    """NDJSON line counter."""

    def test_counts_nonempty_lines(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"id":"1"}\n{"id":"2"}\n\n{"id":"3"}\n')
        assert count_ndjson_lines(f) == 3

    def test_empty_file_returns_zero(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text("")
        assert count_ndjson_lines(f) == 0


class TestCosmosPartitionKeys:
    """Partition key mapping correctness."""

    def test_documents_uses_collection_key(self):
        assert COSMOS_PARTITION_KEYS["documents"] == "/collection"

    def test_per_collection_containers_use_id(self):
        for name in ["sources", "archives", "messages", "threads",
                      "chunks", "summaries", "reports", "user_roles"]:
            assert COSMOS_PARTITION_KEYS[name] == "/id", f"{name} should use /id"

    def test_reports_is_present(self):
        assert "reports" in COSMOS_PARTITION_KEYS


class TestImportMongoDB:
    """MongoDB import with mocked pymongo."""

    def _write_ndjson(self, path: Path, docs: list[dict]):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for doc in docs:
                f.write(json.dumps(doc) + "\n")

    def test_upsert_mode(self, tmp_path):
        """Upsert replaces existing docs."""
        export_dir = tmp_path / "export"
        self._write_ndjson(
            export_dir / "testdb" / "coll.json",
            [{"_id": "1", "v": "a"}, {"_id": "2", "v": "b"}],
        )

        mock_coll = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("pymongo.MongoClient", return_value=mock_client):
            counts = import_mongodb(
                "mongodb://localhost:27017/",
                export_dir, {"testdb": ["coll"]}, "upsert",
            )

        assert counts["testdb.coll"] == 2
        assert mock_coll.replace_one.call_count == 2

    def test_merge_mode_skips_duplicates(self, tmp_path):
        """Merge mode counts skipped duplicates separately."""
        import pymongo.errors

        export_dir = tmp_path / "export"
        self._write_ndjson(
            export_dir / "testdb" / "coll.json",
            [{"_id": "1"}, {"_id": "2"}, {"_id": "3"}],
        )

        mock_coll = MagicMock()
        # First insert succeeds, second is duplicate, third succeeds
        mock_coll.insert_one.side_effect = [
            MagicMock(),
            pymongo.errors.DuplicateKeyError("dup"),
            MagicMock(),
        ]
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("pymongo.MongoClient", return_value=mock_client):
            counts = import_mongodb(
                "mongodb://localhost:27017/",
                export_dir, {"testdb": ["coll"]}, "merge",
            )

        # Only 2 imported, 1 skipped
        assert counts["testdb.coll"] == 2

    def test_normalizes_id_from_id_field(self, tmp_path):
        """Docs with 'id' but no '_id' get _id set from id."""
        export_dir = tmp_path / "export"
        self._write_ndjson(
            export_dir / "testdb" / "coll.json",
            [{"id": "cosmos-id", "data": "x"}],
        )

        mock_coll = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("pymongo.MongoClient", return_value=mock_client):
            import_mongodb(
                "mongodb://localhost:27017/",
                export_dir, {"testdb": ["coll"]}, "upsert",
            )

        # Verify _id was set from id
        replaced_doc = mock_coll.replace_one.call_args[0][1]
        assert replaced_doc["_id"] == "cosmos-id"

    def test_errors_on_missing_id(self, tmp_path):
        """Docs with neither _id nor id are counted as errors."""
        export_dir = tmp_path / "export"
        self._write_ndjson(
            export_dir / "testdb" / "coll.json",
            [{"data": "no-id-here"}],
        )

        mock_coll = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("pymongo.MongoClient", return_value=mock_client):
            counts = import_mongodb(
                "mongodb://localhost:27017/",
                export_dir, {"testdb": ["coll"]}, "upsert",
            )

        # 0 imported (1 error)
        assert counts["testdb.coll"] == 0

    def test_skips_missing_file(self, tmp_path):
        """Collections with no export file are skipped."""
        export_dir = tmp_path / "export"
        export_dir.mkdir()

        mock_client = MagicMock()

        with patch("pymongo.MongoClient", return_value=mock_client):
            counts = import_mongodb(
                "mongodb://localhost:27017/",
                export_dir, {"testdb": ["missing"]}, "upsert",
            )

        assert counts == {}
