# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for scripts/get_data_counts.py.

These tests validate that we use cheap metadata paths:
- MongoDB: db.command('collStats', <collection>)
- Qdrant: /collections/<name> points_count
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import scripts.get_data_counts as mod


def test_build_default_mongo_collection_map_defaults():
    mapping = mod.build_default_mongo_collection_map(include_all=False)
    assert mapping["archives"] == "archives"
    assert mapping["emails"] == "messages"
    assert mapping["chunks"] == "chunks"
    assert mapping["reports"] == "reports"
    assert "threads" not in mapping


def test_build_default_mongo_collection_map_include_all():
    mapping = mod.build_default_mongo_collection_map(include_all=True)
    assert mapping["threads"] == "threads"
    assert mapping["summaries"] == "summaries"
    assert mapping["sources"] == "sources"


def test_get_mongo_collstats_counts_uses_collstats(monkeypatch):
    # Mock MongoClient and returned DB/command
    mock_client = MagicMock()
    mock_db = MagicMock()

    # client[db] -> db
    mock_client.__getitem__.return_value = mock_db

    # ping ok
    mock_client.admin.command.return_value = {"ok": 1}

    # collStats results
    def command_side_effect(cmd, collection_name):
        assert cmd == "collStats"
        return {"count": {"archives": 5, "messages": 10}.get(collection_name, 0)}

    mock_db.command.side_effect = command_side_effect

    monkeypatch.setattr(mod, "_get_mongo_client", lambda uri: mock_client)

    results = mod.get_mongo_collstats_counts(
        mongo_uri="mongodb://example",
        database="copilot",
        collections={"archives": "archives", "emails": "messages"},
    )

    as_dict = {r.name: r.count for r in results}
    assert as_dict == {"archives": 5, "emails": 10}


def test_get_qdrant_points_count_happy_path(monkeypatch):
    def fake_get(url, headers, timeout):
        assert url.endswith("/collections/embeddings")
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"result": {"points_count": 123}}
        return resp

    monkeypatch.setattr(mod.requests, "get", fake_get)

    res = mod.get_qdrant_points_count(host="localhost", port=6333, collection="embeddings")
    assert res.name == "embeddings"
    assert res.count == 123
    assert res.source == "qdrant"


def test_get_qdrant_points_count_handles_error(monkeypatch):
    def fake_get(url, headers, timeout):
        raise RuntimeError("boom")

    monkeypatch.setattr(mod.requests, "get", fake_get)

    res = mod.get_qdrant_points_count(host="localhost", port=6333, collection="embeddings")
    assert res.count is None
    assert res.detail and "boom" in res.detail


def test_parse_azure_metrics_series_counts_dimension_named():
    payload = {
        "value": [
            {
                "timeseries": [
                    {
                        "metadatavalues": [
                            {"name": {"value": "CollectionName"}, "value": "archives"}
                        ],
                        "data": [
                            {"timeStamp": "2026-01-22T00:00:00Z", "maximum": 1},
                            {"timeStamp": "2026-01-22T00:05:00Z", "maximum": 5},
                        ],
                    },
                    {
                        "metadatavalues": [
                            {"name": {"value": "CollectionName"}, "value": "messages"}
                        ],
                        "data": [
                            {"timeStamp": "2026-01-22T00:00:00Z", "maximum": None},
                            {"timeStamp": "2026-01-22T00:05:00Z", "maximum": 10},
                        ],
                    },
                ]
            }
        ]
    }

    counts = mod.parse_azure_metrics_series_counts(payload, dimension_name="CollectionName")
    assert counts == {"archives": 5, "messages": 10}


def test_parse_azure_metrics_series_counts_autodetect_dimension():
    payload = {
        "value": [
            {
                "timeseries": [
                    {
                        "metadatavalues": [
                            {"name": {"value": "SomeDim"}, "value": "chunks"}
                        ],
                        "data": [{"timeStamp": "2026-01-22T00:00:00Z", "average": 7}],
                    }
                ]
            }
        ]
    }

    counts = mod.parse_azure_metrics_series_counts(payload)
    assert counts == {"chunks": 7}


def test_main_azure_metrics_maps_collections(monkeypatch, capsys):
    # Force azure-metrics mode and fake `az monitor metrics list` output.
    def fake_run_az_json(args):
        assert args[:3] == ["monitor", "metrics", "list"]
        return {
            "value": [
                {
                    "timeseries": [
                        {
                            "metadatavalues": [
                                {"name": {"value": "CollectionName"}, "value": "archives"}
                            ],
                            "data": [{"maximum": 2}],
                        },
                        {
                            "metadatavalues": [
                                {"name": {"value": "CollectionName"}, "value": "messages"}
                            ],
                            "data": [{"maximum": 3}],
                        },
                        {
                            "metadatavalues": [
                                {"name": {"value": "CollectionName"}, "value": "chunks"}
                            ],
                            "data": [{"maximum": 4}],
                        },
                        {
                            "metadatavalues": [
                                {"name": {"value": "CollectionName"}, "value": "reports"}
                            ],
                            "data": [{"maximum": 5}],
                        },
                    ]
                }
            ]
        }

    monkeypatch.setattr(mod, "_run_az_json", fake_run_az_json)

    # Avoid calling real Qdrant.
    monkeypatch.setattr(
        mod,
        "get_qdrant_points_count",
        lambda **kwargs: mod.CountResult(name="embeddings", count=6, source="qdrant"),
    )

    rc = mod.main(
        [
            "--mode",
            "azure-metrics",
            "--cosmos-resource-id",
            "/subscriptions/000/resourceGroups/rg/providers/Microsoft.DocumentDB/databaseAccounts/acct",
            "--cosmos-dimension",
            "CollectionName",
            "--format",
            "json",
        ]
    )
    assert rc == 0

    out = capsys.readouterr().out
    data = __import__("json").loads(out)
    assert data["counts"]["archives"] == 2
    assert data["counts"]["emails"] == 3
    assert data["counts"]["chunks"] == 4
    assert data["counts"]["reports"] == 5
    assert data["counts"]["embeddings"] == 6


def test_resolve_cosmos_resource_id_single_account(monkeypatch):
    def fake_run_az_json(args):
        assert args[:2] == ["resource", "list"]
        return [{"name": "acct1", "id": "/subscriptions/1/.../databaseAccounts/acct1"}]

    monkeypatch.setattr(mod, "_run_az_json", fake_run_az_json)
    rid = mod.resolve_cosmos_resource_id_from_resource_group(resource_group="copilot-app-rg")
    assert rid.endswith("/databaseAccounts/acct1")


def test_resolve_cosmos_resource_id_multiple_accounts_requires_name(monkeypatch):
    def fake_run_az_json(args):
        return [
            {"name": "acct1", "id": "/subscriptions/1/.../databaseAccounts/acct1"},
            {"name": "acct2", "id": "/subscriptions/1/.../databaseAccounts/acct2"},
        ]

    monkeypatch.setattr(mod, "_run_az_json", fake_run_az_json)

    with pytest.raises(RuntimeError, match="Multiple Cosmos accounts"):
        mod.resolve_cosmos_resource_id_from_resource_group(resource_group="copilot-app-rg")

    rid = mod.resolve_cosmos_resource_id_from_resource_group(resource_group="copilot-app-rg", account_name="acct2")
    assert rid.endswith("/databaseAccounts/acct2")
